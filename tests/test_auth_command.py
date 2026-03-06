import json

from instagrapi.exceptions import ChallengeRequired
from typer.testing import CliRunner

from ig_cli.config import Config
from ig_cli.main import app


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def login(self, username: str, password: str, verification_code: str = "") -> bool:
        self.calls.append((username, password, verification_code))
        if not verification_code:
            from instagrapi.exceptions import TwoFactorRequired

            raise TwoFactorRequired("2FA required")
        return True

    def get_settings(self) -> dict[str, object]:
        return {"cookies": {"sessionid": "abc"}}

    def account_info(self):
        return type(
            "AccountInfo",
            (),
            {
                "username": "panpan.live",
                "pk": "12345678901",
                "full_name": "Panpan Live",
                "is_private": False,
                "is_verified": False,
            },
        )()


class ChallengeAccountInfoClient(FakeClient):
    def account_info(self):
        raise ChallengeRequired("challenge_required")


class ChallengeLoginClient(FakeClient):
    def login(self, username: str, password: str, verification_code: str = "") -> bool:
        raise ChallengeRequired("challenge_required")


class FalseLoginClient(FakeClient):
    def login(self, username: str, password: str, verification_code: str = "") -> bool:
        self.calls.append((username, password, verification_code))
        return False


class PreservesUuidClient(FakeClient):
    last_instance = None

    def __init__(self) -> None:
        super().__init__()
        self.uuids = None
        self.proxy = None
        PreservesUuidClient.last_instance = self

    def set_uuids(self, uuids):
        self.uuids = uuids

    def set_proxy(self, proxy):
        self.proxy = proxy


class ChallengeClient(FakeClient):
    def account_info(self):
        from instagrapi.exceptions import ChallengeRequired

        raise ChallengeRequired("challenge_required")


class LoginRequiredClient(FakeClient):
    def account_info(self):
        from instagrapi.exceptions import LoginRequired

        raise LoginRequired("login_required")


def test_auth_login_prompts_for_2fa_and_saves_session(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr("ig_cli.commands.auth.Client", FakeClient)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["auth", "login", "--alias", "test", "--default"],
        input="panpan.live\ntest-password-fake\n123456\n",
    )

    assert result.exit_code == 0
    assert "Instagram 2FA code" in result.stdout
    payload = json.loads(result.stdout[result.stdout.index("{") :])
    assert payload["status"] == "logged_in"
    assert payload["alias"] == "test"
    cfg = Config()
    assert cfg.get_default_account() == "test"
    assert cfg.load_session("test") == {"cookies": {"sessionid": "abc"}}


def test_auth_session_reports_saved_session(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.save_session("test", {"cookies": {"sessionid": "abc"}})

    runner = CliRunner()
    result = runner.invoke(app, ["auth", "session", "--alias", "test"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "session_exists"
    assert payload["has_cookies"] is True


def test_auth_session_surfaces_permission_error_as_json(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.save_session("test", {"cookies": {"sessionid": "abc"}})
    cfg.session_path("test").chmod(0o644)

    runner = CliRunner()
    result = runner.invoke(app, ["auth", "session", "--alias", "test"])

    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert "session file" in payload["error"].lower()


def test_auth_session_surfaces_malformed_session_file_as_json(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.session_path("test").write_text("{not json")
    cfg.session_path("test").chmod(0o600)

    runner = CliRunner()
    result = runner.invoke(app, ["auth", "session", "--alias", "test"])

    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert "expecting property name enclosed in double quotes" in payload["error"].lower()


def test_auth_session_rejects_non_mapping_session_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.session_path("test").write_text("null")
    cfg.session_path("test").chmod(0o600)

    runner = CliRunner()
    result = runner.invoke(app, ["auth", "session", "--alias", "test"])

    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert "session file" in payload["error"].lower()
    assert "must contain a json/toml object" in payload["error"].lower()


def test_auth_list_and_logout(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.save_session("test", {"cookies": {"sessionid": "abc"}})
    cfg.set_default_account("test")

    runner = CliRunner()
    list_result = runner.invoke(app, ["auth", "list"])
    assert list_result.exit_code == 0
    list_payload = json.loads(list_result.stdout)
    assert list_payload["accounts"] == ["test"]
    assert list_payload["default"] == "test"

    logout_result = runner.invoke(app, ["auth", "logout", "--alias", "test"])
    assert logout_result.exit_code == 0
    logout_payload = json.loads(logout_result.stdout)
    assert logout_payload["removed"] is True
    assert cfg.session_path("test").exists() is False


def test_auth_whoami_uses_selected_account(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr("ig_cli.commands.auth.get_raw_client", lambda alias: (alias, FakeClient()))

    runner = CliRunner()
    result = runner.invoke(app, ["--account", "test", "auth", "whoami"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["alias"] == "test"
    assert payload["username"] == "panpan.live"


def test_auth_whoami_supports_alias_shorthand(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.save_session("panpan_test", {"cookies": {"sessionid": "abc"}})
    monkeypatch.setattr("ig_cli.commands.auth.get_raw_client", lambda alias: (alias, FakeClient()))

    runner = CliRunner()
    result = runner.invoke(app, ["panpan_test", "auth", "whoami"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["alias"] == "panpan_test"
    assert payload["username"] == "panpan.live"


def test_auth_validate_reports_valid_selected_account(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr("ig_cli.commands.auth.get_raw_client", lambda alias: (alias, FakeClient()))

    runner = CliRunner()
    result = runner.invoke(app, ["--account", "test", "auth", "validate"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "alias": "test",
        "status": "valid",
        "username": "panpan.live",
        "pk": "12345678901",
    }


def test_auth_validate_surfaces_checkpoint_as_json_error(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(
        "ig_cli.commands.auth.get_raw_client",
        lambda alias: (alias, ChallengeAccountInfoClient()),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["auth", "validate", "--account", "test"])

    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert "checkpoint required" in payload["error"].lower()
    assert "test" in payload["error"]


def test_auth_whoami_surfaces_checkpoint_as_json_error(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(
        "ig_cli.commands.auth.get_raw_client",
        lambda alias: (alias, ChallengeAccountInfoClient()),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["auth", "whoami", "--account", "test"])

    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert "checkpoint required" in payload["error"].lower()
    assert "test" in payload["error"]


def test_auth_login_rejects_false_login_result(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr("ig_cli.commands.auth.Client", FalseLoginClient)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["auth", "login", "--alias", "test"],
        input="panpan.live\ntest-password-fake\n",
    )

    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert "instagram login failed" in payload["error"].lower()


def test_auth_login_reuses_saved_uuids_and_proxy_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("IG_CLI_PROXY_TEST", "http://proxy.example:1234")
    cfg = Config()
    cfg.save_session("test", {"uuids": {"phone_id": "phone-1"}})
    monkeypatch.setattr("ig_cli.commands.auth.Client", PreservesUuidClient)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["auth", "login", "--alias", "test"],
        input="panpan.live\ntest-password-fake\n123456\n",
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout[result.stdout.index("{") :])
    assert payload["status"] == "logged_in"
    assert PreservesUuidClient.last_instance.uuids == {"phone_id": "phone-1"}
    assert PreservesUuidClient.last_instance.proxy == "http://proxy.example:1234"


def test_auth_login_normalizes_checkpoint_error(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr("ig_cli.commands.auth.Client", ChallengeLoginClient)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["auth", "login", "--alias", "test"],
        input="panpan.live\ntest-password-fake\n",
    )

    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert "checkpoint required" in payload["error"].lower()
    assert "test" in payload["error"]


def test_auth_help_mentions_proxy_handlers_and_validate():
    runner = CliRunner()
    result = runner.invoke(app, ["auth", "--help"])

    assert result.exit_code == 0
    assert "IG_CLI_PROXY" in result.stdout
    assert "challenge_code_cmd" in result.stdout
    assert "ig auth validate" in result.stdout


def test_auth_validate_surfaces_checkpoint_cleanly(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(
        "ig_cli.commands.auth.get_raw_client", lambda alias: (alias, ChallengeClient())
    )

    runner = CliRunner()
    result = runner.invoke(app, ["--account", "test", "auth", "validate"])

    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert "checkpoint required" in payload["error"].lower()
    assert "test" in payload["error"]


def test_auth_whoami_surfaces_login_required_cleanly(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(
        "ig_cli.commands.auth.get_raw_client", lambda alias: (alias, LoginRequiredClient())
    )

    runner = CliRunner()
    result = runner.invoke(app, ["--account", "test", "auth", "whoami"])

    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert "session for 'test' is no longer valid" in payload["error"].lower()
