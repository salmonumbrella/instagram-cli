import json

from typer.testing import CliRunner

from ig_cli.main import app


def test_raw_methods_lists_known_methods():
    result = CliRunner().invoke(app, ["raw", "methods"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "user_info_by_username" in payload["methods"]


def test_raw_coverage_reports_curated_vs_missing_methods():
    result = CliRunner().invoke(app, ["raw", "coverage"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "user_info_by_username" in payload["covered"]
    assert "media_create_livestream" in payload["covered"]
    assert payload["missing_count"] >= 1


def test_raw_schema_returns_parameter_metadata():
    result = CliRunner().invoke(app, ["raw", "schema", "user_info_by_username"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["name"] == "user_info_by_username"


def test_raw_schema_invalid_method_returns_json_error():
    result = CliRunner().invoke(app, ["raw", "schema", "definitely_not_a_method"])

    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["error"] == "Unknown client method: definitely_not_a_method"


def test_raw_call_invokes_selected_method(monkeypatch):
    class FakeClient:
        def user_info_by_username(self, username: str):
            return {"username": username, "pk": "1"}

    monkeypatch.setattr(
        "ig_cli.commands.raw.get_client_from_ctx", lambda ctx, account: FakeClient()
    )

    result = CliRunner().invoke(
        app,
        [
            "--account",
            "panpan_test",
            "raw",
            "call",
            "user_info_by_username",
            "--arg",
            "username=panpan.live",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["username"] == "panpan.live"


def test_raw_call_rejects_write_methods():
    result = CliRunner().invoke(app, ["raw", "call", "media_delete", "--arg", "media_id=1"])

    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["error"] == "raw call currently supports read-only methods only"


def test_raw_call_rejects_representative_mutating_methods_not_covered_by_client_classifier():
    for method_name in ("direct_media_share", "notification_disable"):
        result = CliRunner().invoke(app, ["raw", "call", method_name])

        assert result.exit_code == 1
        payload = json.loads(result.stderr)
        assert payload["error"] == "raw call currently supports read-only methods only"


def test_raw_call_invocation_errors_return_json_error(monkeypatch):
    class FakeClient:
        def user_info_by_username(self, username: str):
            return {"username": username}

    monkeypatch.setattr(
        "ig_cli.commands.raw.get_client_from_ctx", lambda ctx, account: FakeClient()
    )

    result = CliRunner().invoke(
        app,
        ["raw", "call", "user_info_by_username", "--arg", "missing=nope"],
    )

    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert "unexpected keyword argument 'missing'" in payload["error"]
