from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
DB_PATH = Path(os.getenv("FITNESS_DB_PATH", ROOT / "data" / "fitness.db"))
HEVY_API_KEY = os.getenv("HEVY_API_KEY") or os.getenv("hevy_api_key")
PUSHOVER_USER_KEY = os.getenv("PUSHOVER_USER_KEY")
PUSHOVER_API_TOKEN = os.getenv("PUSHOVER_API_TOKEN")
HEVY_BASE_URL = "https://api.hevyapp.com/v1"
