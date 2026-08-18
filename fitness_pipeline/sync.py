from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from .db import connect, migrate
from .hevy import HevyClient
from .notify import notify_failure


def now() -> str:
    return datetime.now(UTC).isoformat()


def _set_state(conn, key: str, value: str) -> None:
    conn.execute(
        """INSERT INTO sync_state(key,value) VALUES(?,?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP""",
        (key, value),
    )


def upsert_workout(conn, workout: dict) -> None:
    conn.execute(
        """INSERT INTO workouts(
          id,title,routine_id,description,start_time,end_time,hevy_created_at,
          hevy_updated_at,raw_json,deleted_at,synced_at)
        VALUES(:id,:title,:routine_id,:description,:start_time,:end_time,:created_at,
          :updated_at,:raw_json,NULL,:synced_at)
        ON CONFLICT(id) DO UPDATE SET
          title=excluded.title, routine_id=excluded.routine_id,
          description=excluded.description, start_time=excluded.start_time,
          end_time=excluded.end_time, hevy_created_at=excluded.hevy_created_at,
          hevy_updated_at=excluded.hevy_updated_at, raw_json=excluded.raw_json,
          deleted_at=NULL, synced_at=excluded.synced_at""",
        {
            "id": workout["id"],
            "title": workout.get("title") or "Untitled",
            "routine_id": workout.get("routine_id"),
            "description": workout.get("description"),
            "start_time": workout["start_time"],
            "end_time": workout.get("end_time"),
            "created_at": workout.get("created_at"),
            "updated_at": workout.get("updated_at") or now(),
            "raw_json": json.dumps(workout, sort_keys=True),
            "synced_at": now(),
        },
    )
    conn.execute("DELETE FROM exercises WHERE workout_id=?", (workout["id"],))
    for exercise in workout.get("exercises", []):
        exercise_index = exercise["index"]
        conn.execute(
            "INSERT INTO exercises VALUES (?,?,?,?,?,?)",
            (
                workout["id"], exercise_index, exercise.get("exercise_template_id"),
                exercise.get("title") or "Untitled", exercise.get("notes"),
                exercise.get("supersets_id"),
            ),
        )
        for set_ in exercise.get("sets", []):
            conn.execute(
                "INSERT INTO sets VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    workout["id"], exercise_index, set_["index"],
                    set_.get("type", "normal"), set_.get("weight_kg"),
                    set_.get("reps"), set_.get("distance_meters"),
                    set_.get("duration_seconds"), set_.get("rpe"),
                    set_.get("custom_metric"),
                ),
            )


def full_sync(client=None) -> int:
    """Reconcile the cache to a complete Hevy listing, retaining missing rows as deleted."""
    client = client or HevyClient()
    watermark = now()  # Never advance the event cursor beyond data we have fetched.
    workouts = list(client.workouts())
    seen_ids = {workout["id"] for workout in workouts}
    conn = connect()
    try:
        migrate(conn)
        with conn:
            for workout in workouts:
                upsert_workout(conn, workout)
            active_ids = {row[0] for row in conn.execute("SELECT id FROM workouts WHERE deleted_at IS NULL")}
            missing_ids = active_ids - seen_ids
            if missing_ids:
                conn.executemany(
                    "UPDATE workouts SET deleted_at=?, synced_at=? WHERE id=?",
                    [(now(), now(), workout_id) for workout_id in missing_ids],
                )
            _set_state(conn, "last_full_sync", watermark)
            _set_state(conn, "last_event_sync", watermark)
        return len(workouts)
    finally:
        conn.close()


def incremental_sync(client=None) -> int:
    client = client or HevyClient()
    conn = connect()
    try:
        migrate(conn)
        row = conn.execute("SELECT value FROM sync_state WHERE key='last_event_sync'").fetchone()
        since = row[0] if row else "1970-01-01T00:00:00Z"
        watermark = now()  # Events after this instant are intentionally fetched next time.
        events = list(client.events(since))
        with conn:
            for event in events:
                event_type = event.get("type", "").lower()
                if event_type == "deleted":
                    workout_id = event["id"]
                    deleted_at = event.get("deleted_at") or now()
                    conn.execute(
                        "UPDATE workouts SET deleted_at=?, synced_at=? WHERE id=?",
                        (deleted_at, now(), workout_id),
                    )
                elif event_type == "updated":
                    upsert_workout(conn, event["workout"])
                else:
                    raise ValueError(f"Unknown Hevy workout event type: {event_type!r}")
            _set_state(conn, "last_event_sync", watermark)
        return len(events)
    finally:
        conn.close()


def sync(force_full: bool = False, client=None) -> tuple[str, int]:
    conn = connect()
    try:
        migrate(conn)
        row = conn.execute("SELECT value FROM sync_state WHERE key='last_full_sync'").fetchone()
        due = not row or datetime.fromisoformat(row[0]).astimezone(UTC) < datetime.now(UTC) - timedelta(days=7)
    finally:
        conn.close()
    try:
        if force_full or due:
            return "full", full_sync(client)
        return "incremental", incremental_sync(client)
    except Exception as exc:
        notify_failure(str(exc))
        raise
