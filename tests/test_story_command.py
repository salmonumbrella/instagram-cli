import json
from pathlib import Path

from typer.testing import CliRunner

from ig_cli.main import app
from ig_cli.runtime import get_runtime_options


class FakeStoryClient:
    def user_stories(self, user_id: str):
        return [{"pk": "story1", "user_id": user_id}]

    def story_viewers(self, story_pk: str):
        return [{"pk": "viewer1", "story_pk": story_pk}]

    def photo_upload_to_story(self, path: Path, caption: str = ""):
        return {"pk": "story-photo-1", "path": str(path), "caption": caption}

    def video_upload_to_story(self, path: Path, caption: str = ""):
        return {"pk": "story-video-1", "path": str(path), "caption": caption}


def test_story_list_returns_json(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.story.get_client_from_ctx",
        lambda ctx, account: FakeStoryClient(),
    )

    result = CliRunner().invoke(app, ["story", "list", "12345"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == [{"pk": "story1", "user_id": "12345"}]


def test_story_viewers_returns_json(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.story.get_client_from_ctx",
        lambda ctx, account: FakeStoryClient(),
    )

    result = CliRunner().invoke(app, ["story", "viewers", "67890"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == [{"pk": "viewer1", "story_pk": "67890"}]


def test_story_upload_photo_uses_selected_root_account(monkeypatch, tmp_path):
    forwarded = {}
    photo = tmp_path / "story-photo.jpg"
    photo.write_bytes(b"x")

    def fake_get_client_from_ctx(ctx, account):
        forwarded["account"] = account
        forwarded["runtime_account"] = get_runtime_options(ctx).account
        return FakeStoryClient()

    monkeypatch.setattr("ig_cli.commands.story.get_client_from_ctx", fake_get_client_from_ctx)

    result = CliRunner().invoke(
        app,
        [
            "--account",
            "panpan_test",
            "story",
            "upload-photo",
            str(photo),
            "--caption",
            "hello story",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert forwarded["account"] is None
    assert forwarded["runtime_account"] == "panpan_test"
    assert payload == {
        "pk": "story-photo-1",
        "path": str(photo),
        "caption": "hello story",
    }


def test_story_upload_video_uses_selected_account(monkeypatch, tmp_path):
    forwarded = {}
    video = tmp_path / "story-video.mp4"
    video.write_bytes(b"x")

    def fake_get_client_from_ctx(ctx, account):
        forwarded["account"] = account
        return FakeStoryClient()

    monkeypatch.setattr("ig_cli.commands.story.get_client_from_ctx", fake_get_client_from_ctx)

    result = CliRunner().invoke(
        app,
        ["story", "upload-video", str(video), "--caption", "clip", "--account", "panpan_test"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert forwarded["account"] == "panpan_test"
    assert payload == {
        "pk": "story-video-1",
        "path": str(video),
        "caption": "clip",
    }
