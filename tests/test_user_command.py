import json

import pytest
from typer.testing import CliRunner

from ig_cli.main import app


class FakeUserClient:
    def user_info_by_username(self, username: str):
        return FakeUserModel(username)

    def user_followers(self, user_id: str, amount: int = 0):
        return {
            "requested_user_id": user_id,
            "amount": amount,
            "items": {"1": {"username": "follower_a"}},
        }

    def user_following(self, user_id: str, amount: int = 0):
        return {
            "requested_user_id": user_id,
            "amount": amount,
            "items": {"2": {"username": "following_b"}},
        }


class FakeUserModel:
    def __init__(self, username: str) -> None:
        self.username = username

    def model_dump(self):
        return {
            "username": self.username,
            "pk": "12345678901",
            "full_name": "Panpan Live",
        }


def test_user_info_uses_account_from_root_option(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.user.get_client_from_ctx", lambda ctx, account: FakeUserClient()
    )

    runner = CliRunner()
    result = runner.invoke(app, ["--account", "panpan_test", "user", "info", "panpan.live"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["username"] == "panpan.live"
    assert payload["pk"] == "12345678901"


def test_user_followers_returns_json_and_propagates_amount(monkeypatch):
    forwarded = {}

    def fake_get_client_from_ctx(ctx, account):
        forwarded["account"] = account
        return FakeUserClient()

    monkeypatch.setattr("ig_cli.commands.user.get_client_from_ctx", fake_get_client_from_ctx)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["user", "followers", "12345", "--amount", "25", "--account", "panpan_test"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert forwarded["account"] == "panpan_test"
    assert payload["requested_user_id"] == "12345"
    assert payload["amount"] == 25
    assert payload["items"]["1"]["username"] == "follower_a"


def test_user_following_returns_json_with_default_amount(monkeypatch):
    forwarded = {}

    def fake_get_client_from_ctx(ctx, account):
        forwarded["account"] = account
        return FakeUserClient()

    monkeypatch.setattr("ig_cli.commands.user.get_client_from_ctx", fake_get_client_from_ctx)

    runner = CliRunner()
    result = runner.invoke(app, ["user", "following", "67890", "--account", "panpan_test"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert forwarded["account"] == "panpan_test"
    assert payload["requested_user_id"] == "67890"
    assert payload["amount"] == 0
    assert payload["items"]["2"]["username"] == "following_b"


@pytest.mark.parametrize("subcommand", ["followers", "following"])
def test_user_commands_reject_negative_amount(monkeypatch, subcommand):
    monkeypatch.setattr(
        "ig_cli.commands.user.get_client_from_ctx", lambda ctx, account: FakeUserClient()
    )

    runner = CliRunner()
    result = runner.invoke(app, ["user", subcommand, "12345", "--amount", "-1"])

    assert result.exit_code != 0
    assert "Invalid value for '--amount'" in result.output
