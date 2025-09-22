import sqlite3
from distutils.version import LooseVersion as V

def setup_db(conn):
    cur = conn.cursor()

    # Optional: safer defaults for durability/perf
    cur.execute("PRAGMA foreign_keys = ON;")
    cur.execute("PRAGMA journal_mode = WAL;")
    cur.execute("PRAGMA synchronous = NORMAL;")

    # Ensure SQLite version supports generated columns (>= 3.31.0, 2020-01-22)
    cur.execute("SELECT sqlite_version()")
    ver = cur.fetchone()[0]
    if V(ver) < V("3.31.0"):
        raise RuntimeError(
            f"SQLite {ver} does not support generated columns. "
            "Upgrade to >= 3.31.0 or remove the generated column."
        )

    # Helper: SQL for the desired table (with generated column)
    desired_sql = """
    CREATE TABLE workout_sets (
        id TEXT PRIMARY KEY,
        date TEXT,
        workout_name TEXT,
        duration TEXT,
        exercise_name TEXT,
        set_order INTEGER,
        is_warmup GENERATED ALWAYS AS (
            CASE WHEN set_order = -1 THEN 1 ELSE 0 END
        ) VIRTUAL,
        weight REAL,
        reps INTEGER,
        distance REAL,
        seconds INTEGER,
        notes TEXT,
        workout_notes TEXT,
        rpe REAL
    )
    """.strip()

    # Does workout_sets exist?
    cur.execute("""
        SELECT sql FROM sqlite_master
        WHERE type='table' AND name='workout_sets'
    """)
    row = cur.fetchone()

    if row is None:
        # Create fresh with generated column
        cur.execute(desired_sql)
    else:
        current_sql = row[0] or ""
        # If it's already the desired shape (has GENERATED ALWAYS for is_warmup), do nothing.
        has_generated = "is_warmup GENERATED ALWAYS AS" in current_sql
        if not has_generated:
            # Migrate to a new table with the generated column
            cur.execute(desired_sql.replace("workout_sets", "workout_sets_new", 1))

            # Copy data (omit is_warmup since it's generated)
            cur.execute("""
                INSERT INTO workout_sets_new (
                    id, date, workout_name, duration, exercise_name,
                    set_order, weight, reps, distance, seconds,
                    notes, workout_notes, rpe
                )
                SELECT
                    id, date, workout_name, duration, exercise_name,
                    set_order, weight, reps, distance, seconds,
                    notes, workout_notes, rpe
                FROM workout_sets
            """)

            # Swap tables
            cur.execute("DROP TABLE workout_sets")
            cur.execute("ALTER TABLE workout_sets_new RENAME TO workout_sets")

    # Create pushed_set_ids table (simple, id-only)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pushed_set_ids (
            id TEXT PRIMARY KEY
        )
    """)

    conn.commit()
