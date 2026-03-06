import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ig_cli.main import app
from ig_cli.runtime import get_runtime_options


class FakeMediaClient:
    def media_info(self, media_pk: str):
        return {
            "requested_media_pk": media_pk,
            "media_type": 1,
            "caption_text": "panpan post",
        }

    def user_medias(self, user_id: str, amount: int = 0):
        return {
            "requested_user_id": user_id,
            "amount": amount,
            "items": [
                {"pk": "101", "media_type": 1},
                {"pk": "102", "media_type": 8},
            ],
        }

    def photo_upload(self, path: Path, caption: str = ""):
        return {
            "pk": "201",
            "path": str(path),
            "caption": caption,
        }

    def media_delete(self, media_pk: str):
        return media_pk == "987654321"


def test_media_info_returns_json_and_uses_root_account(monkeypatch):
    forwarded = {}

    def fake_get_client_from_ctx(ctx, account):
        forwarded["account"] = account
        forwarded["runtime_account"] = get_runtime_options(ctx).account
        return FakeMediaClient()

    monkeypatch.setattr("ig_cli.commands.media.get_client_from_ctx", fake_get_client_from_ctx)

    runner = CliRunner()
    result = runner.invoke(app, ["--account", "panpan_test", "media", "info", "987654321"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert forwarded["account"] is None
    assert forwarded["runtime_account"] == "panpan_test"
    assert payload["requested_media_pk"] == "987654321"
    assert payload["caption_text"] == "panpan post"


def test_media_user_returns_json_and_propagates_amount(monkeypatch):
    forwarded = {}

    def fake_get_client_from_ctx(ctx, account):
        forwarded["account"] = account
        return FakeMediaClient()

    monkeypatch.setattr("ig_cli.commands.media.get_client_from_ctx", fake_get_client_from_ctx)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["media", "user", "12345", "--amount", "25", "--account", "panpan_test"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert forwarded["account"] == "panpan_test"
    assert payload["requested_user_id"] == "12345"
    assert payload["amount"] == 25
    assert payload["items"][0]["pk"] == "101"


def test_media_user_returns_json_with_default_amount(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.media.get_client_from_ctx", lambda ctx, account: FakeMediaClient()
    )

    runner = CliRunner()
    result = runner.invoke(app, ["media", "user", "67890"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["requested_user_id"] == "67890"
    assert payload["amount"] == 0
    assert payload["items"][1]["pk"] == "102"


@pytest.mark.parametrize("subcommand", ["user"])
def test_media_commands_reject_negative_amount(monkeypatch, subcommand):
    monkeypatch.setattr(
        "ig_cli.commands.media.get_client_from_ctx", lambda ctx, account: FakeMediaClient()
    )

    runner = CliRunner()
    result = runner.invoke(app, ["media", subcommand, "12345", "--amount", "-1"])

    assert result.exit_code != 0
    assert "Invalid value for '--amount'" in result.output


def test_media_upload_photo_uses_selected_root_account(monkeypatch, tmp_path):
    forwarded = {}
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"x")

    def fake_get_client_from_ctx(ctx, account):
        forwarded["account"] = account
        forwarded["runtime_account"] = get_runtime_options(ctx).account
        return FakeMediaClient()

    monkeypatch.setattr("ig_cli.commands.media.get_client_from_ctx", fake_get_client_from_ctx)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--yes",
            "--account",
            "panpan_test",
            "media",
            "upload-photo",
            str(photo),
            "--caption",
            "hello",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert forwarded["account"] is None
    assert forwarded["runtime_account"] == "panpan_test"
    assert payload["pk"] == "201"
    assert payload["path"] == str(photo)
    assert payload["caption"] == "hello"


def test_media_delete_uses_selected_account_and_returns_status(monkeypatch):
    forwarded = {}

    def fake_get_client_from_ctx(ctx, account):
        forwarded["account"] = account
        return FakeMediaClient()

    monkeypatch.setattr("ig_cli.commands.media.get_client_from_ctx", fake_get_client_from_ctx)

    runner = CliRunner()
    result = runner.invoke(app, ["media", "delete", "987654321", "--account", "panpan_test"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert forwarded["account"] == "panpan_test"
    assert payload == {"media_pk": "987654321", "deleted": True, "result": True}
