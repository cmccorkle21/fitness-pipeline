#!/usr/bin/env python3
import sqlite3

import pandas as pd

from muscle_mapping import map_exercise_to_muscle_groups

DB_PATH = "synced_workouts.db"
RAW_TABLE = "workout_sets"
ENRICHED_TABLE = "workout_sets_enriched"  # new table


def main():
    conn = sqlite3.connect(DB_PATH)

    # Create the enriched table (idempotent)
    conn.execute(
        f"""
    CREATE TABLE IF NOT EXISTS {ENRICHED_TABLE} (
        id TEXT PRIMARY KEY,
        date TEXT,
        exercise_name TEXT,
        set_order INTEGER,
        set_index INTEGER,
        is_warmup INTEGER,
        muscle_group_primary TEXT,
        muscle_group_secondary TEXT
    )
    """
    )
    conn.commit()

    # Pull all raw sets (switch to incremental if desired)
    df = pd.read_sql_query(f"SELECT * FROM {RAW_TABLE} ORDER BY date ASC", conn)

    if df.empty:
        print("✅ No rows found in raw table.")
        conn.close()
        return

    # Compute set_index per workout date
    df["set_index"] = df.groupby("date").cumcount()

    # Map muscle groups
    df["muscle_groups"] = df["exercise_name"].apply(map_exercise_to_muscle_groups)

    # Sort muscle groups for visual clarity / priority
    group_priority = {
        "Chest": 1,
        "Back": 1,
        "Delts": 2,
        "Legs": 2,
        "Biceps": 3,
        "Triceps": 3,
        "Abs": 4,
        "Forearms": 4,
    }

    def sort_groups(g):
        if isinstance(g, list):
            return sorted(g, key=lambda x: group_priority.get(x, 99))
        return [g] if isinstance(g, str) else []

    df["muscle_groups"] = df["muscle_groups"].apply(sort_groups)

    # Split into primary/secondary
    def split_groups(groups):
        if not groups:
            return None, None
        if len(groups) == 1:
            return groups[0], None
        return groups[0], groups[1]

    df[["muscle_group_primary", "muscle_group_secondary"]] = df["muscle_groups"].apply(
        lambda g: pd.Series(split_groups(g))
    )

    # Handle warmup flag if it exists in raw table
    is_warmup_col = "is_warmup" if "is_warmup" in df.columns else None

    cols = [
        "id",
        "date",
        "exercise_name",
        "set_order",
        "set_index",
        "muscle_group_primary",
        "muscle_group_secondary",
    ]
    if is_warmup_col:
        cols.insert(5, "is_warmup")  # after set_index

    out = df[cols].copy()

    # Upsert into enriched table
    placeholders = ",".join(["?"] * len(cols))
    collist = ",".join(cols)
    cursor = conn.cursor()
    cursor.executemany(
        f"INSERT OR REPLACE INTO {ENRICHED_TABLE} ({collist}) VALUES ({placeholders})",
        out.itertuples(index=False, name=None),
    )
    conn.commit()

    print(f"✅ Upserted {cursor.rowcount} rows into {ENRICHED_TABLE}.")
    conn.close()


if __name__ == "__main__":
    main()
