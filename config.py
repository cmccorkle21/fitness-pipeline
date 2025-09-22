from dotenv import load_dotenv
import os

load_dotenv()

DROPBOX_TOKEN = os.getenv("DROPBOX_TOKEN")
PUSHOVER_USER_KEY = os.getenv("PUSHOVER_USER_KEY")
PUSHOVER_API_TOKEN = os.getenv("PUSHOVER_API_TOKEN")
