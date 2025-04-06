import sqlite3
import pandas as pd
from muscle_mapping import map_exercise_to_muscle_groups

# Load all distinct exercise names from the DB
conn = sqlite3.connect("synced_workouts.db")
df = pd.read_sql_query("SELECT DISTINCT exercise_name FROM workout_sets", conn)
conn.close()

# Map each exercise to muscle groups
df["muscle_groups"] = df["exercise_name"].apply(map_exercise_to_muscle_groups)

# Sort alphabetically for easier scanning
df.sort_values("exercise_name", inplace=True)

# Print them all
for _, row in df.iterrows():
    name = row["exercise_name"]
    muscles = row["muscle_groups"]
    print(f"{name:<40} → {muscles}")
