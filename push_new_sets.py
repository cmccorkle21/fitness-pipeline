import sqlite3
import pandas as pd
from detect_warmups import detect_warmups
from push_to_notion import push_to_notion_row  # <-- updated version
from muscle_mapping import map_exercise_to_muscle_groups
from notify import send_push

# Connect to SQLite and pull only new rows
conn = sqlite3.connect("synced_workouts.db")

# Ensure the tracking table exists
conn.execute("""
CREATE TABLE IF NOT EXISTS pushed_set_ids (
    id TEXT PRIMARY KEY
)
""")
conn.commit()

# Pull unsynced sets
df = pd.read_sql_query("""
    SELECT *
    FROM workout_sets
    WHERE id NOT IN (SELECT id FROM pushed_set_ids)
    ORDER BY date ASC
""", conn)

if df.empty:
    print("✅ No new sets to push.")
    conn.close()
    exit()

# Compute set_index based on true workout flow
df["set_index"] = df.groupby("date").cumcount()

# Map muscle groups
df["muscle_groups"] = df["exercise_name"].apply(map_exercise_to_muscle_groups)

# Sort muscle groups for visual clarity
group_priority = {
    "Chest": 1, "Back": 1, "Delts": 2, "Legs": 2,
    "Biceps": 3, "Triceps": 3, "Abs": 4, "Forearms": 4
}
df["muscle_groups"] = df["muscle_groups"].apply(
    lambda g: sorted(g, key=lambda x: group_priority.get(x, 99)) if isinstance(g, list) else g
)

# Detect warmups
df = detect_warmups(df)

# Push each row and log successful IDs
pushed = 0

testing = False

if testing:
    print(df[["date", "exercise_name", "set_order", "set_index"]])

if (not testing):
    for _, row in df.iterrows():
        print(f"📅 {row['date']} — {row['exercise_name']} — Set Index: {row['set_index']}")
        success = push_to_notion_row(row)
        if success:
            conn.execute("INSERT OR IGNORE INTO pushed_set_ids (id) VALUES (?)", (row["id"],))
            conn.commit()
            pushed += 1
        else:
            print(f"⚠️ Skipping logging for failed row {row['id']}")

conn.close()
print(f"✅ Successfully pushed {pushed} new sets to Notion.")