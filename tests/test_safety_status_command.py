import json

from typer.testing import CliRunner

from ig_cli.config import Config
from ig_cli.main import app


def test_safety_status_returns_required_json_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.set_default_account("testacct")

    runner = CliRunner()
    result = runner.invoke(app, ["safety", "status"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["account"] == "testacct"
    assert "policy" in payload
    assert "circuit_breaker" in payload
    assert "rate_limit" in payload
    assert "pacing" in payload
    assert "retry" in payload
    assert "write_guard" in payload


def test_safety_status_uses_root_account_option(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(app, ["--account", "testacct", "safety", "status"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["account"] == "testacct"


def test_safety_status_missing_account_message_mentions_local_config(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    runner = CliRunner()

    result = runner.invoke(app, ["safety", "status"])

    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert "ig auth" not in payload["error"]
    assert str(cfg.config_file) in payload["error"]


def test_safety_status_invalid_policy_returns_json_error(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.safety_policy_file.write_text(
        """
[safety.circuit_breaker]
half_open_max_probes = 1
close_after_consecutive_successes = 2
""".strip()
    )
    runner = CliRunner()

    result = runner.invoke(app, ["--account", "testacct", "safety", "status"])

    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert str(cfg.safety_policy_file) in payload["error"]
    assert "close_after_consecutive_successes" in payload["error"]
