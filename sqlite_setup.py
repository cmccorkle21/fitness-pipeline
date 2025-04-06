import sqlite3

conn = sqlite3.connect("synced_workouts.db")
cur = conn.cursor()

cur.execute("""
    CREATE TABLE IF NOT EXISTS workout_sets (
        id TEXT PRIMARY KEY,
        date TEXT,
        workout_name TEXT,
        duration TEXT,
        exercise_name TEXT,
        set_order INTEGER,
        weight REAL,
        reps INTEGER,
        distance REAL,
        seconds INTEGER,
        notes TEXT,
        workout_notes TEXT,
        rpe REAL
    )
    """)

cur.execute("""
CREATE TABLE IF NOT EXISTS pushed_set_ids (
    id TEXT PRIMARY KEY
)
""")
conn.commit()
conn.close()
