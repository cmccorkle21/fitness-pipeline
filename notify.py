# notify.py

from pushover import Client
from config import PUSHOVER_USER_KEY, PUSHOVER_API_TOKEN

client = Client(PUSHOVER_USER_KEY, api_token=PUSHOVER_API_TOKEN)

def send_push(msg: str, title: str = "📡 Pi4one"):
    try:
        client.send_message(msg, title=title)
        print(f"📲 Sent push notification: {title} — {msg}")
    except Exception as e:
        print(f"❌ Failed to send push notification: {e}")
