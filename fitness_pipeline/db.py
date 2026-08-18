from __future__ import annotations
import sqlite3
from pathlib import Path
from .config import DB_PATH, ROOT

def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

def migrate(conn: sqlite3.Connection) -> None:
    migrations = sorted((ROOT / "migrations").glob("*.sql"))
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    applied = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    for migration in migrations:
        if migration.name not in applied:
            conn.executescript(migration.read_text())
            conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (migration.name,))
    conn.commit()
