CREATE TABLE agent_workout_requests (
  request_id TEXT PRIMARY KEY,
  payload_hash TEXT NOT NULL,
  hevy_workout_id TEXT NOT NULL,
  response_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
