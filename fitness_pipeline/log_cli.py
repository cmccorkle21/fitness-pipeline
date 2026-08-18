from __future__ import annotations

import argparse
import json
import sys

from .agent_log import available_exercises, log_workout
from .db import connect, migrate

EXAMPLE = {
    "request_id": "one-off-2026-08-18-upper",
    "date": "2026-08-18",
    "title": "One-off upper body",
    "description": "Optional note",
    "is_private": False,
    "exercises": [
        {"name": "incline dumbbell bench", "sets": 6},
        {
            "template_id": "1B2B1E7C",
            "notes": "Optional exercise note",
            "sets": [
                {"type": "normal", "reps": 10, "weight_lb": 25, "rpe": 8},
                {"type": "normal", "reps": 8, "weight_lb": 25},
            ],
        },
    ],
}

INPUT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "fitness-log add input",
    "type": "object",
    "additionalProperties": False,
    "required": ["request_id", "date", "exercises"],
    "properties": {
        "request_id": {
            "type": "string",
            "minLength": 1,
            "description": "Caller-generated idempotency key. Reuse only when retrying the identical payload.",
        },
        "date": {"type": "string", "format": "date", "description": "Workout day in YYYY-MM-DD format."},
        "title": {"type": "string", "default": "Agent Logged Workout"},
        "description": {"type": "string"},
        "is_private": {"type": "boolean", "default": False},
        "exercises": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "oneOf": [{"required": ["name"]}, {"required": ["template_id"]}],
                "required": ["sets"],
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Exact or uniquely matching exercise title/search phrase.",
                    },
                    "template_id": {
                        "type": "string",
                        "description": "Preferred after using the exercises search command.",
                    },
                    "notes": {"type": "string"},
                    "sets": {
                        "description": "Positive count of empty normal sets, or detailed set objects.",
                        "oneOf": [
                            {"type": "integer", "minimum": 1},
                            {
                                "type": "array",
                                "minItems": 1,
                                "items": {"$ref": "#/$defs/set"},
                            },
                        ],
                    },
                },
            },
        },
    },
    "$defs": {
        "set": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "type": {"enum": ["normal", "warmup", "failure", "dropset"], "default": "normal"},
                "weight_lb": {"type": "number", "description": "Converted to kilograms before sending to Hevy."},
                "weight_kg": {"type": "number"},
                "reps": {"type": "integer", "minimum": 0},
                "rpe": {"enum": [6, 7, 7.5, 8, 8.5, 9, 9.5, 10]},
                "distance_meters": {"type": "integer", "minimum": 0},
                "duration_seconds": {"type": "integer", "minimum": 0},
                "custom_metric": {"type": "number"},
            },
            "not": {"required": ["weight_lb", "weight_kg"]},
        }
    },
}

MAIN_HELP = """\
Create one-off Hevy workouts from a machine-readable JSON object.

Agent workflow:
  1. Search:   fitness-log exercises "incline dumbbell bench" --limit 10
  2. Inspect match, workout_count, set_count, last_used_at, and template_id.
  3. Schema:   fitness-log schema
  4. Validate: fitness-log add --dry-run < workout.json
  5. Create:   fitness-log add < workout.json

Hevy remains canonical. Successful creates are immediately cached in the dashboard DB.
All normal output is JSON. Validation errors are JSON on stderr with exit status 2.
"""

ADD_HELP = f"""\
Read exactly one JSON workout object from stdin. No API write occurs with --dry-run.
A date-only workout is recorded from 12:00 to 12:30 in the server's local timezone.

Required fields:
  request_id  Stable idempotency key. An identical retry returns already_created.
  date        YYYY-MM-DD.
  exercises   Non-empty array. Each item needs name or template_id, plus sets.

Sets may be a positive integer or an array of detailed objects. Supported detailed
fields: type, weight_lb, weight_kg, reps, rpe, distance_meters,
duration_seconds, custom_metric. Do not combine weight_lb and weight_kg.

Example JSON:
{json.dumps(EXAMPLE, indent=2)}

Examples:
  fitness-log schema
  fitness-log add --dry-run < workout.json
  fitness-log add < workout.json
  cat workout.json | fitness-log add
"""

EXERCISES_HELP = """\
Search exercise templates already present in the local Hevy cache. Output is ranked
by text relevance, historical workout count, then recency. Each result includes the
immutable template_id, title, match type, matched terms, workout_count, set_count,
last_used_at, and muscle mappings.

Prefer exact > phrase > all_terms > partial. Among similarly relevant results,
prefer higher workout_count, then newer last_used_at. If materially different
choices remain plausible, ask the user instead of guessing.

Examples:
  fitness-log exercises "pull ups"
  fitness-log exercises "incline dumbbell bench" --limit 10
  fitness-log exercises --limit 50
"""


def _print(value) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fitness-log",
        description=MAIN_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version="fitness-log 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add = subparsers.add_parser(
        "add",
        help="Validate or create a workout from JSON on stdin.",
        description=ADD_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add.add_argument("--dry-run", action="store_true", help="Resolve and validate without writing to Hevy.")

    exercises = subparsers.add_parser(
        "exercises",
        help="Search exercise templates ranked by match, usage, and recency.",
        description=EXERCISES_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    exercises.add_argument("query", nargs="?", help="Optional exercise name or search terms.")
    exercises.add_argument("--limit", type=int, default=20, help="Maximum results to return (default: 20).")

    subparsers.add_parser("schema", help="Print the complete add-input JSON Schema and example as JSON.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "schema":
            _print({
                "command": "fitness-log add",
                "input": "one JSON object on stdin",
                "schema": INPUT_SCHEMA,
                "example": EXAMPLE,
                "discovery_command": "fitness-log exercises QUERY --limit 10",
            })
            return

        if args.command == "exercises":
            conn = connect()
            try:
                migrate(conn)
                if args.limit < 1:
                    raise ValueError("--limit must be at least 1.")
                _print({
                    "query": args.query,
                    "ranking": "text match, workout count, recency",
                    "exercises": available_exercises(conn, args.query, args.limit),
                })
            finally:
                conn.close()
            return

        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("Input must be one JSON object.")
        _print(log_workout(payload, dry_run=args.dry_run))
    except (ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
