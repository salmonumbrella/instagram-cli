from typer.testing import CliRunner

from ig_cli.config import Config
from ig_cli.main import app, rewrite_account_alias_args


def test_rewrite_account_alias_args_for_known_alias(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.save_session("panpan_test", {"cookies": {"sessionid": "abc"}})

    args = rewrite_account_alias_args(["panpan_test", "user", "info", "panpan.live"], cfg)

    assert args == ["--account", "panpan_test", "user", "info", "panpan.live"]


def test_rewrite_account_alias_args_keeps_known_command(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.save_session("panpan_test", {"cookies": {"sessionid": "abc"}})

    args = rewrite_account_alias_args(["auth", "list"], cfg)

    assert args == ["auth", "list"]


def test_rewrite_account_alias_args_keeps_unknown_alias(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()

    args = rewrite_account_alias_args(["amyshop", "user", "info", "panpan.live"], cfg)

    assert args == ["amyshop", "user", "info", "panpan.live"]


def test_rewrite_account_alias_args_supports_root_options_before_alias(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.save_session("panpan_test", {"cookies": {"sessionid": "abc"}})

    args = rewrite_account_alias_args(["--yes", "panpan_test", "raw", "methods"], cfg)

    assert args == ["--yes", "--account", "panpan_test", "raw", "methods"]


def test_rewrite_account_alias_args_preserves_explicit_root_account(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.save_session("panpan_test", {"cookies": {"sessionid": "abc"}})

    args = rewrite_account_alias_args(
        ["--account", "base", "panpan_test", "media", "user", "123"],
        cfg,
    )

    assert args == ["--account", "base", "panpan_test", "media", "user", "123"]


def test_rewrite_account_alias_args_keeps_alias_shorthand_with_trailing_account_option(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.save_session("panpan_test", {"cookies": {"sessionid": "abc"}})

    args = rewrite_account_alias_args(
        ["panpan_test", "auth", "whoami", "-a", "panpan_test"],
        cfg,
    )

    assert args == ["--account", "panpan_test", "auth", "whoami", "-a", "panpan_test"]


def test_root_help_mentions_session_proxy_and_challenge_guidance():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Reuse sessions" in result.stdout
    assert "Keep device identity stable" in result.stdout
    assert "IG_CLI_PROXY" in result.stdout
    assert "challenge_code_cmd" in result.stdout
    assert "Centralized exception handling" in result.stdout
