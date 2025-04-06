from dotenv import load_dotenv
import os

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
DROPBOX_TOKEN = os.getenv("DROPBOX_TOKEN")
PUSHOVER_USER_KEY = os.getenv("PUSHOVER_USER_KEY")
PUSHOVER_API_TOKEN = os.getenv("PUSHOVER_API_TOKEN")

if not NOTION_TOKEN:
    raise ValueError("Missing NOTION_TOKEN in .env")

print(f"Loaded DROPBOX_TOKEN: {DROPBOX_TOKEN[:10]}...")  # Print the first few characters for verification