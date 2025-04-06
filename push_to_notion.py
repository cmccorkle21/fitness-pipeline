from notion_client import Client
from datetime import datetime
from dateutil import parser
import time
import pytz
from config import NOTION_TOKEN, NOTION_DATABASE_ID

notion = Client(auth=NOTION_TOKEN)

def push_to_notion_row(row):

    # Parse and convert to ISO8601 with timezone
    local_tz = pytz.timezone("America/Denver")

    if isinstance(row["date"], str):
        dt = parser.parse(row["date"])
    else:
        dt = row["date"]

    dt = local_tz.localize(dt)  # add tz info if not present
    iso_date = dt.isoformat()

    try:
        page = {
            "parent": {"database_id": NOTION_DATABASE_ID},
            "properties": {
                "Date": {
                    "date": {
                        "start": iso_date
                    }
                },
                "Set Index": {"number": int(row.get("set_index", 0))},
                "Exercise": {
                    "title": [{"text": {"content": row["exercise_name"]}}]
                },
                "Weight": {"number": row["weight"]},
                "Reps": {"number": row["reps"]},
                "Is Warmup": {"checkbox": row.get("is_warmup", False)},
                "Muscle Groups": {
                    "multi_select": [
                        {"name": group.strip()}
                        for group in row.get("muscle_groups", [])
                        if group
                    ]
                },
                "Notes": {
                    "rich_text": [{"text": {"content": str(row.get("notes") or "")}}]
                }
            }
        }

        notion.pages.create(**page)
        time.sleep(0.25)
        return True

    except Exception as e:
        print(f"❌ Failed to push set {row.get('id', 'unknown')}: {e}")
        return False
