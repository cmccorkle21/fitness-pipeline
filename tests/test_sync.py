from fitness_pipeline import db
from fitness_pipeline import sync as sync_module
from fitness_pipeline.sync import upsert_workout

WORKOUT = {
    "id": "w1", "title": "Push", "start_time": "2024-01-01T10:00:00Z",
    "updated_at": "2024-01-01T11:00:00Z",
    "exercises": [{"index": 0, "exercise_template_id": "bench", "title": "Bench Press", "sets": [
        {"index": 0, "type": "normal", "weight_kg": 100, "reps": 5},
        {"index": 1, "type": "warmup", "weight_kg": 60, "reps": 10},
    ]}],
}


def test_migrations_and_workout_upsert(tmp_path):
    conn = db.connect(tmp_path / "fitness.db")
    db.migrate(conn)
    upsert_workout(conn, WORKOUT)
    conn.commit()
    assert conn.execute("select count(*) from workouts").fetchone()[0] == 1
    assert conn.execute("select count(*) from exercises").fetchone()[0] == 1
    assert conn.execute("select count(*) from sets").fetchone()[0] == 2
    changed = {**WORKOUT, "title": "Updated", "exercises": []}
    upsert_workout(conn, changed)
    conn.commit()
    assert conn.execute("select title from workouts").fetchone()[0] == "Updated"
    assert conn.execute("select count(*) from sets").fetchone()[0] == 0


def test_migrations_are_idempotent(tmp_path):
    conn = db.connect(tmp_path / "fitness.db")
    db.migrate(conn)
    db.migrate(conn)
    assert conn.execute("select count(*) from schema_migrations").fetchone()[0] == 3


def test_full_sync_soft_deletes_active_workout_missing_from_hevy(tmp_path, monkeypatch):
    path = tmp_path / "fitness.db"
    conn = db.connect(path)
    db.migrate(conn)
    upsert_workout(conn, {**WORKOUT, "id": "removed"})
    conn.commit()
    conn.close()

    class Client:
        def workouts(self):
            return iter([WORKOUT])

    monkeypatch.setattr(sync_module, "connect", lambda: db.connect(path))
    monkeypatch.setattr(sync_module, "now", lambda: "2025-01-01T00:00:00+00:00")
    assert sync_module.full_sync(Client()) == 1
    check = db.connect(path)
    assert check.execute("select deleted_at from workouts where id='removed'").fetchone()[0] is not None
    assert check.execute("select deleted_at from workouts where id='w1'").fetchone()[0] is None
    assert check.execute("select value from sync_state where key='last_event_sync'").fetchone()[0] == "2025-01-01T00:00:00+00:00"


def test_incremental_sync_handles_updated_deleted_and_uses_fetch_watermark(tmp_path, monkeypatch):
    path = tmp_path / "fitness.db"
    conn = db.connect(path)
    db.migrate(conn)
    upsert_workout(conn, {**WORKOUT, "id": "deleted"})
    conn.execute("insert into sync_state(key,value) values('last_event_sync','2024-01-01T00:00:00Z')")
    conn.commit()
    conn.close()

    class Client:
        requested_since = None
        def events(self, since):
            self.requested_since = since
            return iter([
                {"type": "updated", "workout": WORKOUT},
                {"type": "deleted", "id": "deleted", "deleted_at": "2024-02-01T00:00:00Z"},
            ])

    client = Client()
    monkeypatch.setattr(sync_module, "connect", lambda: db.connect(path))
    monkeypatch.setattr(sync_module, "now", lambda: "2025-02-03T04:05:06+00:00")
    assert sync_module.incremental_sync(client) == 2
    assert client.requested_since == "2024-01-01T00:00:00Z"
    check = db.connect(path)
    assert check.execute("select title from workouts where id='w1'").fetchone()[0] == "Push"
    assert check.execute("select deleted_at from workouts where id='deleted'").fetchone()[0] == "2024-02-01T00:00:00Z"
    assert check.execute("select value from sync_state where key='last_event_sync'").fetchone()[0] == "2025-02-03T04:05:06+00:00"
