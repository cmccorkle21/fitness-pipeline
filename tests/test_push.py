import sqlite3
import pandas as pd
from detect_warmups import detect_warmups
from push_to_notion import push_to_notion

# Step 1: Load 5 rows from your synced SQLite DB
conn = sqlite3.connect("synced_workouts.db")
df = pd.read_sql_query("SELECT * FROM workout_sets LIMIT 5", conn)
conn.close()

# Step 2: Add dummy muscle groups for testing
# Replace with real mapping later
df["muscle_groups"] = [["Chest", "Triceps"]] * len(df)

print("Columns in the DataFrame:")
print(df.columns.tolist())

# Step 3: Detect warmups
df = detect_warmups(df)

# Step 4: Print preview
print("Previewing rows to be sent to Notion:")
print(df[["date", "exercise_name", "weight", "reps", "is_warmup", "muscle_groups"]])

# Step 5: Push to Notion
print("\nPushing to Notion...")
push_to_notion(df)
