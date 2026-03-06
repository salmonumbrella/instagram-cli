import json
import os
import stat

import pytest
import typer
from instagrapi.exceptions import ChallengeRequired, TwoFactorRequired

from ig_cli.client import get_raw_client, resolve_account
from ig_cli.config import Config


def test_resolve_account_error_mentions_local_config(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()

    with pytest.raises(typer.Exit):
        resolve_account(None, cfg)

    payload = json.loads(capsys.readouterr().err)
    assert "ig auth" not in payload["error"]
    assert str(cfg.config_file) in payload["error"]


def test_get_raw_client_error_mentions_local_paths(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.set_default_account("testacct")

    with pytest.raises(typer.Exit):
        get_raw_client("testacct", cfg)

    payload = json.loads(capsys.readouterr().err)
    assert "ig auth" not in payload["error"]
    assert str(cfg.session_path("testacct")) in payload["error"]
    for path in cfg.credential_paths("testacct"):
        assert str(path) in payload["error"]


def test_get_raw_client_rejects_insecure_credential_file(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.set_default_account("testacct")
    credential_path = cfg.credential_paths("testacct")[0]
    credential_path.write_text('username = "testacct"\npassword = "secret"\n')
    os.chmod(credential_path, 0o644)

    with pytest.raises(typer.Exit):
        get_raw_client("testacct", cfg)

    payload = json.loads(capsys.readouterr().err)
    assert "Credential file" in payload["error"]
    assert str(credential_path) in payload["error"]
    assert stat.S_IMODE(credential_path.stat().st_mode) == 0o644


def test_get_raw_client_reuses_saved_session_without_validation_probe(monkeypatch, tmp_path):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.save_session("testacct", {"session": "present"})
    os.chmod(cfg.session_path("testacct"), 0o600)

    class FakeClient:
        def __init__(self) -> None:
            self.settings = None
            self.login_called = False

        def set_settings(self, settings):
            self.settings = settings

        def get_timeline_feed(self):
            raise AssertionError("get_timeline_feed should not be called")

        def login(self, username, password, verification_code=""):
            self.login_called = True
            raise AssertionError("login should not be called when session exists")

    monkeypatch.setattr("ig_cli.client.Client", FakeClient)

    alias, client = get_raw_client("testacct", cfg)

    assert alias == "testacct"
    assert client.settings == {"session": "present"}
    assert client.login_called is False


def test_get_raw_client_applies_proxy_from_alias_env(monkeypatch, tmp_path):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("IG_CLI_PROXY_TESTACCT", "http://proxy.example:1234")
    cfg = Config()
    cfg.save_session("testacct", {"session": "present"})
    os.chmod(cfg.session_path("testacct"), 0o600)

    class FakeClient:
        def __init__(self) -> None:
            self.settings = None
            self.proxy = None

        def set_settings(self, settings):
            self.settings = settings

        def set_proxy(self, proxy):
            self.proxy = proxy

    monkeypatch.setattr("ig_cli.client.Client", FakeClient)

    alias, client = get_raw_client("testacct", cfg)

    assert alias == "testacct"
    assert client.proxy == "http://proxy.example:1234"


def test_get_raw_client_configures_challenge_handler_from_runtime_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.save_session("testacct", {"session": "present"})
    os.chmod(cfg.session_path("testacct"), 0o600)
    cfg._save_config({"accounts": {"testacct": {"challenge_code_cmd": "echo 123456"}}})

    class FakeClient:
        def __init__(self) -> None:
            self.settings = None
            self.challenge_code_handler = None
            self.handle_exception = None

        def set_settings(self, settings):
            self.settings = settings

    monkeypatch.setattr("ig_cli.client.Client", FakeClient)

    alias, client = get_raw_client("testacct", cfg)

    assert alias == "testacct"
    assert callable(client.challenge_code_handler)
    assert callable(client.handle_exception)


def test_get_raw_client_applies_credential_runtime_settings_even_with_session(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.save_session("testacct", {"session": "present"})
    os.chmod(cfg.session_path("testacct"), 0o600)
    credential_path = cfg.credential_paths("testacct")[1]
    credential_path.write_text(
        json.dumps(
            {
                "proxy": "http://cred-proxy.example:8080",
                "challenge_code_cmd": "echo 123456",
            }
        )
    )
    os.chmod(credential_path, 0o600)

    class FakeClient:
        def __init__(self) -> None:
            self.settings = None
            self.proxy = None
            self.challenge_code_handler = None

        def set_settings(self, settings):
            self.settings = settings

        def set_proxy(self, proxy):
            self.proxy = proxy

    monkeypatch.setattr("ig_cli.client.Client", FakeClient)

    alias, client = get_raw_client("testacct", cfg)

    assert alias == "testacct"
    assert client.proxy == "http://cred-proxy.example:8080"
    assert callable(client.challenge_code_handler)


def test_get_raw_client_does_not_fallback_to_credentials_when_session_exists(monkeypatch, tmp_path):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.save_session("testacct", {"session": "stale"})
    os.chmod(cfg.session_path("testacct"), 0o600)
    credential_path = cfg.credential_paths("testacct")[1]
    credential_path.write_text(json.dumps({"username": "testacct", "password": "secret"}))
    os.chmod(credential_path, 0o600)

    class FakeClient:
        def __init__(self) -> None:
            self.settings = None
            self.login_called = False

        def set_settings(self, settings):
            self.settings = settings

        def login(self, username, password, verification_code=""):
            self.login_called = True

    monkeypatch.setattr("ig_cli.client.Client", FakeClient)

    alias, client = get_raw_client("testacct", cfg)

    assert alias == "testacct"
    assert client.settings == {"session": "stale"}
    assert client.login_called is False


def test_get_raw_client_does_not_fallback_when_session_file_is_empty_dict(monkeypatch, tmp_path):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.save_session("testacct", {})
    os.chmod(cfg.session_path("testacct"), 0o600)
    credential_path = cfg.credential_paths("testacct")[1]
    credential_path.write_text(json.dumps({"username": "testacct", "password": "secret"}))
    os.chmod(credential_path, 0o600)

    class FakeClient:
        def __init__(self) -> None:
            self.settings = None
            self.login_called = False

        def set_settings(self, settings):
            self.settings = settings

        def login(self, username, password, verification_code=""):
            self.login_called = True

    monkeypatch.setattr("ig_cli.client.Client", FakeClient)

    alias, client = get_raw_client("testacct", cfg)

    assert alias == "testacct"
    assert client.settings == {}
    assert client.login_called is False


def test_get_raw_client_uses_credentials_when_no_session_exists(monkeypatch, tmp_path):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    credential_path = cfg.credential_paths("testacct")[1]
    credential_path.write_text(json.dumps({"username": "testacct", "password": "secret"}))
    os.chmod(credential_path, 0o600)

    class FakeClient:
        def __init__(self) -> None:
            self.logged_in = False

        def login(self, username, password, verification_code=""):
            self.logged_in = True
            self.username = username
            return True

        def get_settings(self):
            return {"session": "fresh"}

    monkeypatch.setattr("ig_cli.client.Client", FakeClient)

    alias, client = get_raw_client("testacct", cfg)

    assert alias == "testacct"
    assert client.logged_in is True
    assert cfg.load_session("testacct") == {"session": "fresh"}


def test_get_raw_client_surfaces_checkpoint_during_credential_login(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    credential_path = cfg.credential_paths("testacct")[1]
    credential_path.write_text(json.dumps({"username": "testacct", "password": "secret"}))
    os.chmod(credential_path, 0o600)

    class FakeClient:
        def login(self, username, password, verification_code=""):
            raise ChallengeRequired("challenge_required")

    monkeypatch.setattr("ig_cli.client.Client", FakeClient)

    with pytest.raises(typer.Exit):
        get_raw_client("testacct", cfg)

    payload = json.loads(capsys.readouterr().err)
    assert "checkpoint required" in payload["error"].lower()
    assert "testacct" in payload["error"]


def test_get_raw_client_rejects_false_login_result(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    credential_path = cfg.credential_paths("testacct")[1]
    credential_path.write_text(json.dumps({"username": "testacct", "password": "secret"}))
    os.chmod(credential_path, 0o600)

    class FakeClient:
        def login(self, username, password, verification_code=""):
            return False

    monkeypatch.setattr("ig_cli.client.Client", FakeClient)

    with pytest.raises(typer.Exit):
        get_raw_client("testacct", cfg)

    payload = json.loads(capsys.readouterr().err)
    assert "did not produce a valid instagram login" in payload["error"].lower()


def test_get_raw_client_surfaces_two_factor_required_during_credential_login(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    credential_path = cfg.credential_paths("testacct")[1]
    credential_path.write_text(json.dumps({"username": "testacct", "password": "secret"}))
    os.chmod(credential_path, 0o600)

    class FakeClient:
        def login(self, username, password, verification_code=""):
            raise TwoFactorRequired("2FA required")

    monkeypatch.setattr("ig_cli.client.Client", FakeClient)

    with pytest.raises(typer.Exit):
        get_raw_client("testacct", cfg)

    payload = json.loads(capsys.readouterr().err)
    assert "interactive 2fa" in payload["error"].lower()
    assert "ig auth login --alias testacct" in payload["error"]


def test_get_raw_client_surfaces_op_read_failures(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    credential_path = cfg.credential_paths("testacct")[1]
    credential_path.write_text(
        json.dumps({"username": "testacct", "password_op_ref": "op://vault/item"})
    )
    os.chmod(credential_path, 0o600)

    class FakeResult:
        returncode = 1
        stdout = ""
        stderr = "item not found"

    monkeypatch.setattr("ig_cli.client.subprocess.run", lambda *args, **kwargs: FakeResult())

    with pytest.raises(typer.Exit):
        get_raw_client("testacct", cfg)

    payload = json.loads(capsys.readouterr().err)
    assert "failed to resolve secret" in payload["error"].lower()
    assert "item not found" in payload["error"].lower()


def test_get_raw_client_surfaces_missing_op_binary(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    credential_path = cfg.credential_paths("testacct")[1]
    credential_path.write_text(
        json.dumps({"username": "testacct", "password_op_ref": "op://vault/item"})
    )
    os.chmod(credential_path, 0o600)

    def raise_missing_op(*args, **kwargs):
        raise FileNotFoundError("op not found")

    monkeypatch.setattr("ig_cli.client.subprocess.run", raise_missing_op)

    with pytest.raises(typer.Exit):
        get_raw_client("testacct", cfg)

    payload = json.loads(capsys.readouterr().err)
    assert "1password cli `op` is not installed" in payload["error"].lower()


def test_get_raw_client_surfaces_malformed_session_file(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.session_path("testacct").write_text("{not json")
    os.chmod(cfg.session_path("testacct"), 0o600)

    with pytest.raises(typer.Exit):
        get_raw_client("testacct", cfg)

    payload = json.loads(capsys.readouterr().err)
    assert "expecting property name enclosed in double quotes" in payload["error"].lower()


def test_get_raw_client_rejects_non_mapping_session_payload(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.session_path("testacct").write_text("null")
    os.chmod(cfg.session_path("testacct"), 0o600)

    with pytest.raises(typer.Exit):
        get_raw_client("testacct", cfg)

    payload = json.loads(capsys.readouterr().err)
    assert "session file" in payload["error"].lower()
    assert "must contain a json/toml object" in payload["error"].lower()


def test_get_raw_client_surfaces_malformed_credential_file(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    credential_path = cfg.credential_paths("testacct")[1]
    credential_path.write_text("{not json")
    os.chmod(credential_path, 0o600)

    with pytest.raises(typer.Exit):
        get_raw_client("testacct", cfg)

    payload = json.loads(capsys.readouterr().err)
    assert "expecting property name enclosed in double quotes" in payload["error"].lower()


def test_get_raw_client_rejects_non_mapping_credential_payload(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    credential_path = cfg.credential_paths("testacct")[1]
    credential_path.write_text('"oops"')
    os.chmod(credential_path, 0o600)

    with pytest.raises(typer.Exit):
        get_raw_client("testacct", cfg)

    payload = json.loads(capsys.readouterr().err)
    assert "credential file" in payload["error"].lower()
    assert "must contain a json/toml object" in payload["error"].lower()
