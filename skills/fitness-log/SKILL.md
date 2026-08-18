---
name: fitness-log
description: Search the user's Hevy exercise history and record one-off workout volume through the fitness-log CLI. Use when the user asks to log, record, add, or backfill a workout, exercises, or sets outside the Hevy app.
compatibility: Requires the fitness-log executable in PATH; the CLI encapsulates database and Hevy API access.
---

# Fitness workout logging

Record user-described one-off workouts in Hevy. Hevy is canonical; successful entries are also cached in the fitness dashboard database.

## Non-negotiable rules

- Search before selecting an exercise template. Do not invent template IDs.
- Never infer weights, reps, RPE, set types, or dates the user did not provide. A numeric set count is valid without those details.
- Ask for clarification when the date, set count, or exercise choice is materially ambiguous.
- Always dry-run before creating.
- Never claim success unless `fitness-log add` returns `status: created` or `status: already_created` with a `hevy_workout_id`.
- Reuse the same `request_id` only when retrying the identical payload. Never reuse it for changed data.

## Discover the interface

The CLI is self-documenting. If anything is unclear or validation fails, inspect it instead of guessing:

```bash
fitness-log --help
fitness-log add --help
fitness-log exercises --help
fitness-log schema
```

`fitness-log schema` returns the complete input JSON Schema and an example as machine-readable JSON.

## Required workflow

### 1. Search every requested exercise

```bash
fitness-log exercises "USER EXERCISE WORDS" --limit 10
```

Interpret results in this order:

1. Prefer `match: exact`, then `phrase`, then `all_terms`, then `partial`.
2. Among similarly relevant choices, prefer greater `workout_count`.
3. If usage is similar, prefer newer `last_used_at`.
4. Use `primary_muscle` and `secondary_muscle` as supporting context.
5. If materially different choices remain plausible, present concise candidates and ask the user. Do not silently choose.

Use the selected immutable `template_id` in the creation payload.

### 2. Build one JSON payload

Required fields:

- `request_id`: stable caller-generated idempotency key, preferably including date and a short workout slug.
- `date`: `YYYY-MM-DD`.
- `exercises`: non-empty array; each item has the selected `template_id` and `sets`.

Optional workout fields are `title`, `description`, and `is_private`. `sets` may be a positive integer or an array of detailed set objects.

Example:

```json
{
  "request_id": "one-off-2026-08-18-upper",
  "date": "2026-08-18",
  "title": "One-off upper body",
  "exercises": [
    {"template_id": "07B38369", "sets": 6},
    {"template_id": "1B2B1E7C", "sets": 6}
  ]
}
```

### 3. Dry-run

Send the payload on stdin:

```bash
fitness-log add --dry-run < /tmp/workout.json
```

Check the returned date, resolved exercise titles, template IDs, and set counts. Correct the payload and repeat the dry-run if needed.

### 4. Create using the identical payload

```bash
fitness-log add < /tmp/workout.json
```

Report the returned `hevy_workout_id`. If the command fails, report the error and do not imply the workout was logged.

## Detailed sets

A numeric value such as `"sets": 6` creates six normal sets without reps or weight. Detailed sets can include:

```json
{"type":"normal","reps":10,"weight_lb":50,"rpe":8}
```

Supported fields are `type`, `reps`, `weight_lb`, `weight_kg`, `rpe`, `distance_meters`, `duration_seconds`, and `custom_metric`. Do not provide both `weight_lb` and `weight_kg`. Consult `fitness-log schema` for types and enums.

If only a date is given, the CLI records 12:00–12:30 in repono's local timezone.
