from __future__ import annotations
import requests
from .config import HEVY_API_KEY, HEVY_BASE_URL

class HevyClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or HEVY_API_KEY
        if not self.api_key:
            raise RuntimeError("Set HEVY_API_KEY in .env or the environment.")
        self.session = requests.Session()
        self.session.headers["api-key"] = self.api_key

    def _get(self, path: str, **params):
        response = self.session.get(f"{HEVY_BASE_URL}{path}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def workouts(self):
        first = self._get("/workouts", page=1, pageSize=10)
        yield from first["workouts"]
        for page in range(2, first["page_count"] + 1):
            yield from self._get("/workouts", page=page, pageSize=10)["workouts"]

    def events(self, since: str):
        first = self._get("/workouts/events", page=1, pageSize=10, since=since)
        yield from first.get("events", [])
        for page in range(2, first.get("page_count", 1) + 1):
            yield from self._get("/workouts/events", page=page, pageSize=10, since=since).get("events", [])

    def workout(self, workout_id: str):
        return self._get(f"/workouts/{workout_id}")
