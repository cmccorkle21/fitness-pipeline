# Fitness pipeline — Hevy edition

A private Streamlit dashboard for Hevy training history. Hevy is the canonical source; the local SQLite database is a queryable cache with normalized workout/exercise/set records and raw API payloads.

## Setup

```bash
uv sync
cp .env.example .env # add HEVY_API_KEY
uv run fitness-sync --full --seed-mappings
uv run streamlit run app.py
```

The initial full sync imports all history. Normal `fitness-sync` runs use Hevy workout events; a full reconciliation is automatically performed at least weekly. Deleted Hevy workouts are soft-deleted locally and excluded from analytics.

Weights are stored in kilograms exactly as Hevy supplies them. The current weighted-sets dashboard has no weight display; future displays should render pounds by default without changing stored data.

## Agent workout CLI

`fitness-log` is a small JSON interface for AI agents to create one-off workouts in Hevy. Hevy remains canonical, and successful creations are immediately written to the dashboard cache. Each request requires a unique `request_id`; retrying the same payload returns the existing Hevy workout instead of creating a duplicate. Run `fitness-log --help`, `fitness-log add --help`, or `fitness-log schema` for a self-contained interface reference and machine-readable JSON Schema.

Search exercise names or template IDs:

```bash
uv run fitness-log exercises "incline dumbbell bench" --limit 10
```

Results include text-match quality, historical workout/set counts, last-used time, and muscle mappings. They are ranked first by text relevance, then usage frequency, then recency so an agent can favor exercises you actually use. A ready-to-use agent workflow is provided in `skills/fitness-log/SKILL.md`.

Validate without writing:

```bash
cat <<'JSON' | uv run fitness-log add --dry-run
{
  "request_id": "one-off-2026-08-18-upper",
  "date": "2026-08-18",
  "title": "One-off upper body",
  "exercises": [
    {"name": "incline dumbbell bench", "sets": 6},
    {"name": "pull ups", "sets": 6}
  ]
}
JSON
```

Remove `--dry-run` to create the workout. A numeric `sets` value creates that many normal sets without weight or reps. For detailed sets, provide an array such as `"sets": [{"reps": 10, "weight_lb": 50}, {"reps": 8, "weight_lb": 55}]`. The CLI also accepts `weight_kg`, `rpe`, set `type`, duration, and distance fields. Date-only entries use 12:00–12:30 in the server's local timezone.

Exercise resolution accepts an exact title or a unique word/substring match. Ambiguous names fail with candidates instead of guessing; `template_id` can always be supplied directly.

Install the CLI entry points in `~/.local/bin` as editable tools so they track this checkout:

```bash
uv tool install --editable /home/cole/source/fitness-pipeline --force
```

## Manual muscle mappings

Mappings are keyed by immutable Hevy exercise-template IDs, not titles. In **Settings**, set a primary muscle and optional secondary muscle. Non-warmup primary sets count as 1.0 and secondary attribution as 0.5. Unmapped templates are deliberately excluded and listed in the Settings queue. The one-time seed button applies the retired Strong title rules and their historical primary/secondary ordering; review every seeded mapping.

## Deployment on repono

The included `deploy/` units run Streamlit and a persistent nightly 00:10 server-local-time sync. Install only after reviewing paths:

```bash
sudo cp deploy/fitness-dashboard.service deploy/fitness-sync.service deploy/fitness-sync.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fitness-dashboard.service fitness-sync.timer
```

`Persistent=true` catches up a missed nightly sync. The sync code chooses a full reconciliation when the prior full sync is at least seven days old. Systemd journal logs failures; configured Pushover credentials also receive a best-effort failure alert. Keep this private to LAN/VPN; the app has no authentication.

## Data and migrations

Default database path: `data/fitness.db` (override `FITNESS_DB_PATH`). Ordered SQL files in `migrations/` are tracked in `schema_migrations` and applied atomically before use. NAS backups are the intended backup layer. Do not commit `.env` or the database.

## Tests

```bash
uv run pytest
```
