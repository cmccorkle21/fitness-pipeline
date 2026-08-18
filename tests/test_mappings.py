from fitness_pipeline.db import connect, migrate
from fitness_pipeline.mappings import legacy_groups, seed_mappings
from fitness_pipeline.sync import upsert_workout


def test_seed_uses_template_id_and_retired_primary_secondary_order(tmp_path):
    conn = connect(tmp_path / "fitness.db")
    migrate(conn)
    upsert_workout(conn, {
        "id": "w", "title": "x", "start_time": "2024-01-01T00:00:00Z",
        "exercises": [{"index": 0, "exercise_template_id": "template-1", "title": "Barbell Bench Press", "sets": []}],
    })
    conn.commit()
    assert seed_mappings(conn) == 1
    row = conn.execute("select primary_muscle,secondary_muscle from exercise_mappings where template_id='template-1'").fetchone()
    assert tuple(row) == ("Chest", "Triceps")


def test_retired_rules_and_priority_are_preserved():
    assert legacy_groups("Lat Pulldown") == ["Back", "Biceps"]
    assert legacy_groups("Dumbbell Bench Press") == ["Chest", "Triceps"]
    assert legacy_groups("Face Pull") == ["Shoulders"]
    assert legacy_groups("Band Pull Apart") == ["Rehab"]
    # Preserve the old source's concatenated literal typo: this generic name was unmatched.
    assert legacy_groups("Hamstring Curl") == []
    assert legacy_groups("Lying Leg Curl") == ["Legs"]


def test_soft_delete_is_retained_for_audit(tmp_path):
    conn = connect(tmp_path / "fitness.db")
    migrate(conn)
    upsert_workout(conn, {"id": "w", "title": "x", "start_time": "2024-01-01T00:00:00Z", "exercises": []})
    conn.commit()
    conn.execute("update workouts set deleted_at='2024-01-02T00:00:00Z' where id='w'")
    conn.commit()
    assert conn.execute("select count(*) from workouts where deleted_at is null").fetchone()[0] == 0
    assert conn.execute("select raw_json from workouts where id='w'").fetchone()[0]
