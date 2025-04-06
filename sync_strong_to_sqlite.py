import dropbox
import pandas as pd
import sqlite3
import hashlib
from io import BytesIO
from config import DROPBOX_TOKEN

DROPBOX_FILE_PATH = "/strong.csv"  # inside /Apps/strong-workout-sync
LOCAL_DB_PATH = "synced_workouts.db"

print(f"Using Dropbox file path: {DROPBOX_FILE_PATH}")

# 🧠 Hash function to detect duplicates
def hash_row(row):
    row_str = "|".join(str(v) for v in row.values)
    return hashlib.sha256(row_str.encode("utf-8")).hexdigest()

# 📥 Download CSV from Dropbox
def download_csv():
    #dbx = dropbox.Dropbox(DROPBOX_TOKEN)
    dbx = dropbox.Dropbox("sl.u.AFqRztAOmNYXVsLOv8VpLWw9lg3gaqEMpWSjs2PGS1sPjJN7p0-fZ08ZL8CauYTWqiYRV-fJRvLAmga9mfFX3maitX4p5DEtbeRpHIqAdJhgqoWaYlZ_S9pB1p3SHue9LNYDeefAMM0l3wmLC6CoAnWPaIB0F0yvIyDYlPbVwV1JuXLTcAYPevCPnORYScdITvdLYmI_YgMvkfnieQR5IAF5wUmLVLTuYxbF6h2rRd630xrlMSloG_i16hJYwZ2Kw152LN1BXdpUVK7aYMxy2Xk25xZ9EjZJ3h4OYwcz1j6l_ChEkwoG5TxzhbRPToF_sE4EpqH6oQyBUJsvcJp0JbB0FbCTcRkmahivfcjVWD0Dmbbw25BOG2N3TaahDRod3fal5OAHQjTThg5hB9_hylF93t4mhK1yJ9AFJHhRT48UkMwkwiQ1WKVTRVPJcKooH-mHhjCOZOer_tC_-fZGql7GnSU2USbZiYddRu535aafSWFOw4iv3Hr3WxRjQ03gP1cROAOOWuL5JQV23D_OW9ILNG_X0j8Ke10UJqaONUXG9Zc5sXWGneodTf8FFlXegRHdEZSV1mFIqc6K_fdWdCZNYIEU5Sj3r9yBHwlDN4vPUXdXxbA_08-O5RTypOXhlpuBxrmfBUOiUj9LvTji1Rme2pfSUdTplGWRjtawRyh2ClXJLSrs61gQo2_bH-1DVmSDomtHJHzlWzSdKX13u69NW15wEyEj6FjgPy8-1-ScC2cPusJ7c1MuujISfo2Df7k3bizW_Liz2KVi1kQnahoRB7coRhxw87O6j8jZcBcMIkr3Gexv6353AQ1wFy1wOjQWKgbOeS_1SnkQ1pMoz2LUZhypb1hVPaGNnnMzd4oBiAp64OGx4arvbTX7ZOibJMhG75aVHXMf3SLiTkZA5V59hMnAYPy_u_eUJbx3LcD00md0fyp3305wLygcV1LOCdOsyF5TPvalOThWyX_TlT7b1AzBSLQruESpWHOV4ieyNeZmzyZUZ2h8SwZlQ72ewJ42fPhBbMqcIgMWpDwk5nrxmPtP4OHpcPXhuNDLWG6jzjlDoJ-25UWnLRycQUQ6QuCggYJb2Qp6D--MMpjgRzj_52sIA18J5BmYHQmNeZHf9lrrtjc8_rdiAvKao1sh_6tetOXh5Xrnoa7uv-Wm3xo4evjq01dW-aYB3FDq_r1vKv2A-9uQvc3mHU6ZrKddGogO8hnPx5zA4IG-rzyCKDJTTyNZArhCz3gCmD3CACXjxqa1d3h6lEs7cXYAIUsfUP7QFbtI5dQ9NYVW_54_BrcHKyC5iGLLeeMjUxD8sWb3LA")
    _, res = dbx.files_download(DROPBOX_FILE_PATH)
    return BytesIO(res.content)

# 🗃 Create SQLite DB and insert new sets
def sync_to_sqlite(csv_io):
    df = pd.read_csv(csv_io)

    conn = sqlite3.connect(LOCAL_DB_PATH)
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

    new_rows = 0

    for _, row in df.iterrows():
        row_id = hash_row(row)
        try:
            cur.execute("""
                INSERT INTO workout_sets (id, date, workout_name, duration,
                exercise_name, set_order, weight, reps, distance, seconds,
                notes, workout_notes, rpe)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row_id,
                row["Date"],
                row["Workout Name"],
                row["Duration"],
                row["Exercise Name"],
                int(row["Set Order"]),
                float(row["Weight"]) if not pd.isna(row["Weight"]) else None,
                int(row["Reps"]) if not pd.isna(row["Reps"]) else None,
                float(row["Distance"]) if not pd.isna(row["Distance"]) else None,
                int(row["Seconds"]) if not pd.isna(row["Seconds"]) else None,
                row["Notes"],
                row["Workout Notes"],
                float(row["RPE"]) if not pd.isna(row["RPE"]) else None
            ))
            new_rows += 1
        except sqlite3.IntegrityError:
            pass  # already synced

    conn.commit()
    conn.close()

    print(f"✅ Synced {new_rows} new set(s) to SQLite.")

# 🏁 Run it
if __name__ == "__main__":
    csv_io = download_csv()
    sync_to_sqlite(csv_io)
