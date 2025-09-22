import dropbox
from dropbox.exceptions import ApiError
import pandas as pd
import sqlite3
import hashlib
from io import BytesIO
from dropbox_auth import get_dropbox_access_token
from log_config import get_logger

logger = get_logger("sync_strong")

DROPBOX_FILE_PATH = "/strong.csv"  # inside /Apps/strong-workout-sync
LOCAL_DB_PATH = "synced_workouts.db"
access_token = get_dropbox_access_token()

print(f"Using Dropbox file path: {DROPBOX_FILE_PATH}")

# 🧠 Hash function to detect duplicates
def hash_row(row):
    row_str = "|".join(str(v) for v in row.values)
    return hashlib.sha256(row_str.encode("utf-8")).hexdigest()

# 📥 Download CSV from Dropbox
def download_csv():
    logger.info(f"🔄 Downloading {DROPBOX_FILE_PATH} from Dropbox...")
    dbx = dropbox.Dropbox(access_token)
    
    try:
        metadata, res = dbx.files_download(DROPBOX_FILE_PATH)
        return BytesIO(res.content)

    except ApiError as e:
        if isinstance(e.error, dropbox.files.DownloadError):
            logger.error(f"❌ Dropbox DownloadError: {e}")
        else:
            logger.error(f"❌ Dropbox API Error: {e}")
        raise

    except Exception as e:
        logger.error(f"❌ Unexpected Error: {e}")
        raise
    logger.info("🔄 Download complete.")
    return BytesIO(res.content)

# 🗃 Create SQLite DB and insert new sets
def sync_to_sqlite(csv_io):
    logger.info("🟢 Starting sync from Strong export...")
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
    logger.info(f"✅ Synced {new_rows} new set(s) to SQLite.")

# 🏁 Run it
if __name__ == "__main__":
    csv_io = download_csv()
    sync_to_sqlite(csv_io)
