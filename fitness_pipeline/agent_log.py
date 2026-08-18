from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, time, timedelta
from typing import Any

from .db import connect, migrate
from .hevy import HevyClient
from .sync import upsert_workout

REQUEST_MARKER = "fitness-agent-request"
SET_FIELDS = {"type", "weight_kg", "reps", "distance_meters", "duration_seconds", "custom_metric", "rpe"}
SET_TYPES = {"warmup", "normal", "failure", "dropset"}


def _normalized(value: str) -> str:
    words = re.sub(r"[^a-z0-9]+", " ", value.casefold()).split()
    words = [
        word[:-1] if len(word) >= 3 and word.endswith("s") and not word.endswith("ss") and word != "abs" else word
        for word in words
    ]
    return " ".join(words)


def available_exercises(conn, query: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    """Return exercise templates ranked by textual match, usage, then recency."""
    rows = conn.execute(
        """SELECT e.template_id, MAX(e.title) AS title,
                  COUNT(DISTINCT e.workout_id) AS workout_count,
                  COUNT(s.set_index) AS set_count,
                  MAX(w.start_time) AS last_used_at,
                  MAX(m.primary_muscle) AS primary_muscle,
                  MAX(m.secondary_muscle) AS secondary_muscle
           FROM exercises e
           JOIN workouts w ON w.id=e.workout_id AND w.deleted_at IS NULL
           LEFT JOIN sets s ON s.workout_id=e.workout_id AND s.exercise_index=e.exercise_index
           LEFT JOIN exercise_mappings m ON m.template_id=e.template_id
           WHERE e.template_id IS NOT NULL
           GROUP BY e.template_id"""
    ).fetchall()
    exercises = [dict(row) for row in rows]
    if query:
        needle = _normalized(query)
        query_words = set(needle.split())
        ranked = []
        for item in exercises:
            title = _normalized(item["title"])
            title_words = set(title.split())
            overlap = len(query_words & title_words)
            if title == needle:
                match_type, match_rank = "exact", 4
            elif needle in title:
                match_type, match_rank = "phrase", 3
            elif query_words and query_words.issubset(title_words):
                match_type, match_rank = "all_terms", 2
            elif overlap:
                match_type, match_rank = "partial", 1
            else:
                continue
            item.update(match=match_type, matched_terms=overlap)
            ranked.append((match_rank, item))
        exercises = [
            item for _, item in sorted(
                ranked,
                key=lambda pair: (
                    -pair[0],
                    -pair[1]["matched_terms"],
                    -pair[1]["workout_count"],
                    pair[1]["last_used_at"] or "",
                    pair[1]["title"].casefold(),
                ),
                reverse=False,
            )
        ]
        # Within identical text relevance, prefer recency descending after frequency.
        start = 0
        while start < len(exercises):
            signature = (exercises[start]["match"], exercises[start]["matched_terms"], exercises[start]["workout_count"])
            end = start + 1
            while end < len(exercises) and (
                exercises[end]["match"], exercises[end]["matched_terms"], exercises[end]["workout_count"]
            ) == signature:
                end += 1
            exercises[start:end] = sorted(exercises[start:end], key=lambda item: item["last_used_at"] or "", reverse=True)
            start = end
    else:
        exercises.sort(key=lambda item: item["title"].casefold())
        exercises.sort(key=lambda item: item["last_used_at"] or "", reverse=True)
        exercises.sort(key=lambda item: item["workout_count"], reverse=True)
    return exercises[:limit] if limit is not None else exercises


def resolve_exercise(conn, exercise: dict[str, Any]) -> tuple[str, str]:
    if exercise.get("template_id"):
        row = conn.execute(
            "SELECT MAX(title) AS title FROM exercises WHERE template_id=?",
            (str(exercise["template_id"]),),
        ).fetchone()
        if not row or not row["title"]:
            raise ValueError(f"Unknown exercise template_id: {exercise['template_id']}")
        return str(exercise["template_id"]), row["title"]

    name = str(exercise.get("name", "")).strip()
    if not name:
        raise ValueError("Each exercise requires either name or template_id.")
    all_exercises = available_exercises(conn)
    normalized = _normalized(name)
    exact = [item for item in all_exercises if _normalized(item["title"]) == normalized]
    substring = [item for item in all_exercises if normalized in _normalized(item["title"])]
    query_words = set(normalized.split())
    token_matches = [
        item for item in all_exercises
        if query_words and query_words.issubset(set(_normalized(item["title"]).split()))
    ]
    matches = exact or substring or token_matches
    if len(matches) == 1:
        return matches[0]["template_id"], matches[0]["title"]
    if not matches:
        raise ValueError(f"No exercise matches {name!r}. Use `fitness-log exercises QUERY`.")
    candidates = ", ".join(f"{item['title']} ({item['template_id']})" for item in matches[:10])
    raise ValueError(f"Ambiguous exercise {name!r}; candidates: {candidates}")


def _build_set(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = dict(raw or {})
    if "weight_lb" in raw:
        if "weight_kg" in raw:
            raise ValueError("A set cannot specify both weight_lb and weight_kg.")
        raw["weight_kg"] = round(float(raw.pop("weight_lb")) * 0.45359237, 4)
    unknown = set(raw) - SET_FIELDS
    if unknown:
        raise ValueError(f"Unsupported set fields: {', '.join(sorted(unknown))}")
    raw.setdefault("type", "normal")
    if raw["type"] not in SET_TYPES:
        raise ValueError(f"Invalid set type: {raw['type']}")
    return {field: raw[field] for field in SET_FIELDS if field in raw}


def _build_sets(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, int) and not isinstance(value, bool):
        if value < 1:
            raise ValueError("Set count must be at least 1.")
        return [_build_set() for _ in range(value)]
    if isinstance(value, list) and value:
        if not all(isinstance(item, dict) for item in value):
            raise ValueError("sets must be a positive integer or a non-empty array of objects.")
        return [_build_set(item) for item in value]
    raise ValueError("sets must be a positive integer or a non-empty array of objects.")


def build_workout(conn, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        workout_date = date.fromisoformat(str(payload["date"]))
    except (KeyError, ValueError) as exc:
        raise ValueError("date is required in YYYY-MM-DD format.") from exc
    exercises = payload.get("exercises")
    if not isinstance(exercises, list) or not exercises:
        raise ValueError("exercises must be a non-empty array.")

    start = datetime.combine(workout_date, time(12, 0)).astimezone()
    end = start + timedelta(minutes=30)
    built_exercises = []
    for exercise in exercises:
        if not isinstance(exercise, dict):
            raise ValueError("Each exercise must be an object.")
        template_id, title = resolve_exercise(conn, exercise)
        built_exercises.append(
            {
                "exercise_template_id": template_id,
                "superset_id": None,
                "notes": exercise.get("notes"),
                "sets": _build_sets(exercise.get("sets")),
                "resolved_title": title,
            }
        )

    request_id = str(payload.get("request_id", "")).strip()
    if not request_id:
        raise ValueError("request_id is required for duplicate protection.")
    description = str(payload.get("description", "")).strip()
    marker = f"[{REQUEST_MARKER}:{request_id}]"
    description = f"{description}\n\n{marker}".strip()
    return {
        "title": str(payload.get("title") or "Agent Logged Workout"),
        "description": description,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "is_private": bool(payload.get("is_private", False)),
        "exercises": built_exercises,
    }


def log_workout(payload: dict[str, Any], *, client=None, dry_run: bool = False) -> dict[str, Any]:
    request_id = str(payload.get("request_id", "")).strip()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload_hash = hashlib.sha256(canonical.encode()).hexdigest()
    conn = connect()
    migrate(conn)
    try:
        existing = conn.execute(
            "SELECT payload_hash,hevy_workout_id,response_json FROM agent_workout_requests WHERE request_id=?",
            (request_id,),
        ).fetchone() if request_id else None
        if existing:
            if existing["payload_hash"] != payload_hash:
                raise ValueError("request_id was already used with a different payload.")
            return {"status": "already_created", "request_id": request_id, "hevy_workout_id": existing["hevy_workout_id"]}

        workout = build_workout(conn, payload)
        api_workout = {**workout, "exercises": [{k: v for k, v in exercise.items() if k != "resolved_title"} for exercise in workout["exercises"]]}
        if dry_run:
            return {"status": "dry_run", "request_id": request_id, "workout": workout}

        response = (client or HevyClient()).create_workout(api_workout)
        created = response.get("workout", response)
        if not isinstance(created, dict) or not created.get("id"):
            raise RuntimeError("Hevy created the workout but returned an unexpected response.")
        with conn:
            upsert_workout(conn, created)
            conn.execute(
                """INSERT INTO agent_workout_requests(request_id,payload_hash,hevy_workout_id,response_json)
                   VALUES(?,?,?,?)""",
                (request_id, payload_hash, created["id"], json.dumps(response, sort_keys=True)),
            )
        return {"status": "created", "request_id": request_id, "hevy_workout_id": created["id"]}
    finally:
        conn.close()
