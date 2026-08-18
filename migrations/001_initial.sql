CREATE TABLE sync_state (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE workouts (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, routine_id TEXT, description TEXT, start_time TEXT NOT NULL,
  end_time TEXT, hevy_created_at TEXT, hevy_updated_at TEXT NOT NULL, raw_json TEXT NOT NULL,
  deleted_at TEXT, synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE exercises (
  workout_id TEXT NOT NULL REFERENCES workouts(id) ON DELETE CASCADE, exercise_index INTEGER NOT NULL,
  template_id TEXT, title TEXT NOT NULL, notes TEXT, superset_id INTEGER, PRIMARY KEY (workout_id, exercise_index)
);
CREATE TABLE sets (
  workout_id TEXT NOT NULL, exercise_index INTEGER NOT NULL, set_index INTEGER NOT NULL, set_type TEXT NOT NULL,
  weight_kg REAL, reps REAL, distance_meters REAL, duration_seconds REAL, rpe REAL, custom_metric REAL,
  PRIMARY KEY (workout_id, exercise_index, set_index),
  FOREIGN KEY (workout_id, exercise_index) REFERENCES exercises(workout_id, exercise_index) ON DELETE CASCADE
);
CREATE TABLE exercise_mappings (
  template_id TEXT PRIMARY KEY, exercise_title TEXT NOT NULL, primary_muscle TEXT NOT NULL,
  secondary_muscle TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_workouts_active_start ON workouts(deleted_at, start_time);
CREATE INDEX idx_exercises_template ON exercises(template_id);
