import sqlite3
import pandas as pd
from detect_warmups import detect_warmups
from push_to_notion import push_to_notion
from muscle_mapping import map_exercise_to_muscle_groups

# Step 1: Load rows from SQLite (full export ordered by Strong)
conn = sqlite3.connect("synced_workouts.db")
df = pd.read_sql_query("""
    SELECT * FROM workout_sets
    WHERE DATE(date) = DATE('now', 'localtime')
    ORDER BY date ASC
""", conn)
conn.close()

# Step 3: Add set_index per day
df["set_index"] = df.groupby("date").cumcount()

# Step 4: Muscle group mapping
df["muscle_groups"] = df["exercise_name"].apply(map_exercise_to_muscle_groups)

# Step 5: Sort multiple muscle groups (visual clarity only)
group_priority = {
    "Chest": 1,
    "Back": 1,
    "Delts": 2,
    "Legs": 2,
    "Biceps": 3,
    "Triceps": 3,
    "Abs": 4,
    "Forearms": 4
}

df["muscle_groups"] = df["muscle_groups"].apply(
    lambda g: sorted(g, key=lambda x: group_priority.get(x, 99)) if isinstance(g, list) else g
)

# Step 6: Warmup detection
df = detect_warmups(df)

print(df[["date", "exercise_name", "set_order", "set_index"]])

# Step 7: Push to Notion
push_to_notion(df)
