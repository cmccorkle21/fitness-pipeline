from fitness_pipeline.log_cli import EXAMPLE, INPUT_SCHEMA, build_parser


def test_schema_documents_required_agent_fields():
    assert INPUT_SCHEMA["required"] == ["request_id", "date", "exercises"]
    assert "sets" in INPUT_SCHEMA["properties"]["exercises"]["items"]["required"]
    assert EXAMPLE["exercises"][0]["sets"] == 6


def test_help_is_self_describing():
    help_text = build_parser().format_help()
    assert "fitness-log exercises" in help_text
    assert "fitness-log schema" in help_text
    assert "--dry-run" in help_text
