import pytest

from fitness_pipeline import agent_log, db
from fitness_pipeline.sync import upsert_workout


TEMPLATE_WORKOUT = {
    "id": "old",
    "title": "Training",
    "start_time": "2024-01-01T10:00:00Z",
    "updated_at": "2024-01-01T11:00:00Z",
    "exercises": [
        {"index": 0, "exercise_template_id": "incline-db", "title": "Incline Bench Press (Dumbbell)", "sets": []},
        {"index": 1, "exercise_template_id": "pull-up", "title": "Pull Up", "sets": []},
    ],
}

PAYLOAD = {
    "request_id": "agent-2024-02-03-a",
    "date": "2024-02-03",
    "title": "One-off upper body",
    "exercises": [
        {"name": "Incline Bench Press (Dumbbell)", "sets": 6},
        {"name": "Pull Up", "sets": 6},
    ],
}


def prepared_db(path):
    conn = db.connect(path)
    db.migrate(conn)
    upsert_workout(conn, TEMPLATE_WORKOUT)
    conn.commit()
    return conn


def test_build_workout_resolves_titles_and_expands_sets(tmp_path):
    conn = prepared_db(tmp_path / "fitness.db")
    workout = agent_log.build_workout(conn, PAYLOAD)
    assert workout["exercises"][0]["exercise_template_id"] == "incline-db"
    assert len(workout["exercises"][0]["sets"]) == 6
    assert workout["start_time"].startswith("2024-02-03T12:00:00")
    assert "fitness-agent-request:agent-2024-02-03-a" in workout["description"]
    assert agent_log.resolve_exercise(conn, {"name": "incline dumbbell bench"})[0] == "incline-db"
    assert agent_log.resolve_exercise(conn, {"name": "pull ups"})[0] == "pull-up"


def test_exercise_search_ranks_usage_then_recency(tmp_path):
    conn = prepared_db(tmp_path / "fitness.db")
    for number, started in [(2, "2024-02-01T10:00:00Z"), (3, "2024-03-01T10:00:00Z")]:
        upsert_workout(conn, {
            **TEMPLATE_WORKOUT,
            "id": f"extra-{number}",
            "start_time": started,
            "exercises": [{
                "index": 0,
                "exercise_template_id": "incline-db",
                "title": "Incline Bench Press (Dumbbell)",
                "sets": [{"index": 0, "type": "normal", "reps": 10}],
            }],
        })
    conn.commit()
    results = agent_log.available_exercises(conn, "bench", limit=5)
    assert results[0]["template_id"] == "incline-db"
    assert results[0]["workout_count"] == 3
    assert results[0]["set_count"] == 2
    assert results[0]["last_used_at"] == "2024-03-01T10:00:00Z"
    assert results[0]["match"] == "phrase"


def test_log_is_idempotent(tmp_path, monkeypatch):
    path = tmp_path / "fitness.db"
    prepared_db(path).close()
    monkeypatch.setattr(agent_log, "connect", lambda: db.connect(path))

    class Client:
        calls = 0

        def create_workout(self, workout):
            self.calls += 1
            exercises = []
            for exercise_index, exercise in enumerate(workout["exercises"]):
                sets = [{**set_, "index": set_index} for set_index, set_ in enumerate(exercise["sets"])]
                exercises.append({
                    **exercise,
                    "index": exercise_index,
                    "title": "Incline Bench Press (Dumbbell)" if exercise_index == 0 else "Pull Up",
                    "sets": sets,
                })
            return {
                **workout,
                "id": "created-1",
                "created_at": "2024-02-03T12:30:00Z",
                "updated_at": "2024-02-03T12:30:00Z",
                "exercises": exercises,
            }

    client = Client()
    first = agent_log.log_workout(PAYLOAD, client=client)
    second = agent_log.log_workout(PAYLOAD, client=client)
    assert first["status"] == "created"
    assert second == {"status": "already_created", "request_id": PAYLOAD["request_id"], "hevy_workout_id": "created-1"}
    assert client.calls == 1


def test_create_accepts_workout_id_envelope(tmp_path, monkeypatch):
    path = tmp_path / "fitness.db"
    prepared_db(path).close()
    monkeypatch.setattr(agent_log, "connect", lambda: db.connect(path))

    class Client:
        def create_workout(self, workout):
            return {"workout": "created-from-id"}

        def workout(self, workout_id):
            return {
                **TEMPLATE_WORKOUT,
                "id": workout_id,
                "created_at": "2024-02-03T12:30:00Z",
                "updated_at": "2024-02-03T12:30:00Z",
            }

    result = agent_log.log_workout(PAYLOAD, client=Client())
    assert result["status"] == "created"
    assert result["hevy_workout_id"] == "created-from-id"


def test_unknown_response_recovers_by_request_marker(tmp_path, monkeypatch):
    path = tmp_path / "fitness.db"
    prepared_db(path).close()
    monkeypatch.setattr(agent_log, "connect", lambda: db.connect(path))

    class Client:
        def create_workout(self, workout):
            return {"success": True}

        def find_workout_by_marker(self, marker):
            return {
                **TEMPLATE_WORKOUT,
                "id": "recovered-1",
                "description": marker,
                "created_at": "2024-02-03T12:30:00Z",
                "updated_at": "2024-02-03T12:30:00Z",
            }

    result = agent_log.log_workout(PAYLOAD, client=Client())
    assert result == {"status": "created", "request_id": PAYLOAD["request_id"], "hevy_workout_id": "recovered-1"}


def test_uncertain_attempt_blocks_automatic_retry(tmp_path, monkeypatch):
    path = tmp_path / "fitness.db"
    prepared_db(path).close()
    monkeypatch.setattr(agent_log, "connect", lambda: db.connect(path))

    class Client:
        calls = 0

        def create_workout(self, workout):
            self.calls += 1
            return {"success": True}

    client = Client()
    first = agent_log.log_workout(PAYLOAD, client=client)
    second = agent_log.log_workout(PAYLOAD, client=client)
    assert first["status"] == "uncertain"
    assert second["status"] == "uncertain"
    assert client.calls == 1


def test_request_id_cannot_be_reused_for_different_payload(tmp_path, monkeypatch):
    path = tmp_path / "fitness.db"
    conn = prepared_db(path)
    conn.execute(
        "INSERT INTO agent_workout_requests(request_id,payload_hash,hevy_workout_id,response_json) VALUES(?,?,?,?)",
        (PAYLOAD["request_id"], "different", "w1", "{}"),
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(agent_log, "connect", lambda: db.connect(path))
    with pytest.raises(ValueError, match="different payload"):
        agent_log.log_workout(PAYLOAD, dry_run=True)
