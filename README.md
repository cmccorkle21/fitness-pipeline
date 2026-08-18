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
