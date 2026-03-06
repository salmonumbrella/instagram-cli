import json

from typer.testing import CliRunner

from ig_cli.main import app
from ig_cli.runtime import get_runtime_options


class FakeLiveClient:
    def media_create_livestream(self, title: str = "Instagram Live"):
        return {
            "broadcast_id": "123",
            "stream_server": "rtmps://live-upload.instagram.com:443/rtmp/",
            "stream_key": "123?s_bl=1&s_tids=1",
        }

    def media_start_livestream(self, broadcast_id: str):
        return True

    def media_end_livestream(self, broadcast_id: str):
        return False

    def media_get_livestream_info(self, broadcast_id: str):
        return {"broadcast_id": broadcast_id, "status": "running"}

    def media_get_livestream_comments(self, broadcast_id: str):
        return [{"pk": "comment1", "broadcast_id": broadcast_id}]

    def media_get_livestream_viewers(self, broadcast_id: str):
        return [{"pk": "viewer1", "broadcast_id": broadcast_id}]


class FakeUploadUrlLiveClient(FakeLiveClient):
    def media_create_livestream(self, title: str = "Instagram Live"):
        return {
            "broadcast_id": 123,
            "upload_url": "rtmps://live-upload.instagram.com:443/rtmp/123?s_bl=1&s_tids=1",
        }


class FakePortCollisionUploadUrlLiveClient(FakeLiveClient):
    def media_create_livestream(self, title: str = "Instagram Live"):
        return {
            "broadcast_id": 443,
            "upload_url": "rtmps://live-upload.instagram.com:443/rtmp/443?s_bl=1&s_tids=1",
        }


class FakeQueryCollisionUploadUrlLiveClient(FakeLiveClient):
    def media_create_livestream(self, title: str = "Instagram Live"):
        return {
            "broadcast_id": 123,
            "upload_url": "rtmps://live-upload.instagram.com:443/rtmp/999?s_bl=1&next=/123",
        }


class FakeKeylessUploadUrlLiveClient(FakeLiveClient):
    def media_create_livestream(self, title: str = "Instagram Live"):
        return {
            "broadcast_id": 123,
            "upload_url": "rtmps://live-upload.instagram.com:443/rtmp/",
        }


class FakePathlessUploadUrlLiveClient(FakeLiveClient):
    def media_create_livestream(self, title: str = "Instagram Live"):
        return {
            "broadcast_id": 123,
            "upload_url": "rtmps://live-upload.instagram.com:443",
        }


class FakeSingleSegmentUploadUrlLiveClient(FakeLiveClient):
    def media_create_livestream(self, title: str = "Instagram Live"):
        return {
            "broadcast_id": 123,
            "upload_url": "rtmps://live-upload.instagram.com:443/rtmp",
        }


class FakeSchemelessUploadUrlLiveClient(FakeLiveClient):
    def media_create_livestream(self, title: str = "Instagram Live"):
        return {
            "broadcast_id": 123,
            "upload_url": "live-upload.instagram.com/rtmp/123?s_bl=1",
        }


class FakeRootRelativeUploadUrlLiveClient(FakeLiveClient):
    def media_create_livestream(self, title: str = "Instagram Live"):
        return {
            "broadcast_id": 123,
            "upload_url": "/rtmp/123?s_bl=1",
        }


class FakeProtocolRelativeUploadUrlLiveClient(FakeLiveClient):
    def media_create_livestream(self, title: str = "Instagram Live"):
        return {
            "broadcast_id": 123,
            "upload_url": "//live-upload.instagram.com/rtmp/123?s_bl=1",
        }


class FakePartialCreateLiveClient(FakeLiveClient):
    def media_create_livestream(self, title: str = "Instagram Live"):
        return {
            "broadcast_id": 123,
            "stream_server": "rtmps://live-upload.instagram.com:443/rtmp/",
            "stream_key": None,
            "upload_url": "bad",
        }


class FakeDictActionLiveClient(FakeLiveClient):
    def media_start_livestream(self, broadcast_id: str):
        return {"status": "started", "note": "already normalized"}


class FakeDictActionMissingBroadcastLiveClient(FakeLiveClient):
    def media_start_livestream(self, broadcast_id: str):
        return {"broadcast_id": None, "status": "started"}


class FakeEndDictActionLiveClient(FakeLiveClient):
    def media_end_livestream(self, broadcast_id: str):
        return {"status": "ended", "note": "already normalized"}


class FakeEndDictActionMissingBroadcastLiveClient(FakeLiveClient):
    def media_end_livestream(self, broadcast_id: str):
        return {"broadcast_id": None, "status": "ended"}


class FakeStringActionLiveClient(FakeLiveClient):
    def media_start_livestream(self, broadcast_id: str):
        return "failed"


class FakeEndStringActionLiveClient(FakeLiveClient):
    def media_end_livestream(self, broadcast_id: str):
        return "error"


class FakeStartFalseLiveClient(FakeLiveClient):
    def media_start_livestream(self, broadcast_id: str):
        return False


class FakeEndTrueLiveClient(FakeLiveClient):
    def media_end_livestream(self, broadcast_id: str):
        return True


def test_live_create_preserves_real_instagrapi_shape(monkeypatch):
    forwarded = {}

    def fake_get_client_from_ctx(ctx, account):
        forwarded["account"] = account
        forwarded["runtime_account"] = get_runtime_options(ctx).account
        return FakeLiveClient()

    monkeypatch.setattr("ig_cli.commands.live.get_client_from_ctx", fake_get_client_from_ctx)

    result = CliRunner().invoke(
        app,
        ["--account", "panpan_test", "live", "create", "--title", "My Live"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert forwarded["account"] is None
    assert forwarded["runtime_account"] == "panpan_test"
    assert payload == {
        "broadcast_id": "123",
        "stream_server": "rtmps://live-upload.instagram.com:443/rtmp/",
        "stream_key": "123?s_bl=1&s_tids=1",
    }


def test_live_create_derives_stream_fields_from_upload_url(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx", lambda ctx, account: FakeUploadUrlLiveClient()
    )

    result = CliRunner().invoke(app, ["live", "create"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "broadcast_id": 123,
        "upload_url": "rtmps://live-upload.instagram.com:443/rtmp/123?s_bl=1&s_tids=1",
        "stream_server": "rtmps://live-upload.instagram.com:443/rtmp/",
        "stream_key": "123?s_bl=1&s_tids=1",
    }


def test_live_create_upload_url_fallback_ignores_port_number_matches(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx",
        lambda ctx, account: FakePortCollisionUploadUrlLiveClient(),
    )

    result = CliRunner().invoke(app, ["live", "create"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "broadcast_id": 443,
        "upload_url": "rtmps://live-upload.instagram.com:443/rtmp/443?s_bl=1&s_tids=1",
        "stream_server": "rtmps://live-upload.instagram.com:443/rtmp/",
        "stream_key": "443?s_bl=1&s_tids=1",
    }


def test_live_create_upload_url_fallback_ignores_query_param_matches(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx",
        lambda ctx, account: FakeQueryCollisionUploadUrlLiveClient(),
    )

    result = CliRunner().invoke(app, ["live", "create"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "broadcast_id": 123,
        "upload_url": "rtmps://live-upload.instagram.com:443/rtmp/999?s_bl=1&next=/123",
        "stream_server": "rtmps://live-upload.instagram.com:443/rtmp/",
        "stream_key": "999?s_bl=1&next=/123",
    }


def test_live_create_keyless_upload_url_preserves_raw_value(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx",
        lambda ctx, account: FakeKeylessUploadUrlLiveClient(),
    )

    result = CliRunner().invoke(app, ["live", "create"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "broadcast_id": 123,
        "upload_url": "rtmps://live-upload.instagram.com:443/rtmp/",
        "stream_server": "rtmps://live-upload.instagram.com:443/rtmp/",
        "stream_key": "",
    }


def test_live_create_pathless_upload_url_preserves_raw_value(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx",
        lambda ctx, account: FakePathlessUploadUrlLiveClient(),
    )

    result = CliRunner().invoke(app, ["live", "create"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "broadcast_id": 123,
        "upload_url": "rtmps://live-upload.instagram.com:443",
        "stream_server": "rtmps://live-upload.instagram.com:443",
        "stream_key": "",
    }


def test_live_create_single_segment_upload_url_preserves_raw_value(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx",
        lambda ctx, account: FakeSingleSegmentUploadUrlLiveClient(),
    )

    result = CliRunner().invoke(app, ["live", "create"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "broadcast_id": 123,
        "upload_url": "rtmps://live-upload.instagram.com:443/rtmp",
        "stream_server": "rtmps://live-upload.instagram.com:443/rtmp",
        "stream_key": "",
    }


def test_live_create_schemeless_upload_url_preserves_raw_value(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx",
        lambda ctx, account: FakeSchemelessUploadUrlLiveClient(),
    )

    result = CliRunner().invoke(app, ["live", "create"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "broadcast_id": 123,
        "upload_url": "live-upload.instagram.com/rtmp/123?s_bl=1",
        "stream_server": "live-upload.instagram.com/rtmp/123?s_bl=1",
        "stream_key": "",
    }


def test_live_create_root_relative_upload_url_preserves_raw_value(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx",
        lambda ctx, account: FakeRootRelativeUploadUrlLiveClient(),
    )

    result = CliRunner().invoke(app, ["live", "create"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "broadcast_id": 123,
        "upload_url": "/rtmp/123?s_bl=1",
        "stream_server": "/rtmp/123?s_bl=1",
        "stream_key": "",
    }


def test_live_create_protocol_relative_upload_url_preserves_raw_value(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx",
        lambda ctx, account: FakeProtocolRelativeUploadUrlLiveClient(),
    )

    result = CliRunner().invoke(app, ["live", "create"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "broadcast_id": 123,
        "upload_url": "//live-upload.instagram.com/rtmp/123?s_bl=1",
        "stream_server": "//live-upload.instagram.com/rtmp/123?s_bl=1",
        "stream_key": "",
    }


def test_live_create_preserves_existing_stream_server_when_upload_url_is_malformed(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx",
        lambda ctx, account: FakePartialCreateLiveClient(),
    )

    result = CliRunner().invoke(app, ["live", "create"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "broadcast_id": 123,
        "stream_server": "rtmps://live-upload.instagram.com:443/rtmp/",
        "stream_key": "",
        "upload_url": "bad",
    }


def test_live_start_normalizes_boolean_true_result(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx", lambda ctx, account: FakeLiveClient()
    )

    result = CliRunner().invoke(app, ["live", "start", "123"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {"broadcast_id": "123", "success": True, "status": "started"}


def test_live_start_normalizes_boolean_false_result(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx", lambda ctx, account: FakeStartFalseLiveClient()
    )

    result = CliRunner().invoke(app, ["live", "start", "123"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {"broadcast_id": "123", "success": False, "status": "start_failed"}


def test_live_start_preserves_structured_result(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx", lambda ctx, account: FakeDictActionLiveClient()
    )

    result = CliRunner().invoke(app, ["live", "start", "123"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "broadcast_id": "123",
        "status": "started",
        "note": "already normalized",
    }


def test_live_start_fills_missing_broadcast_id_in_structured_result(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx",
        lambda ctx, account: FakeDictActionMissingBroadcastLiveClient(),
    )

    result = CliRunner().invoke(app, ["live", "start", "123"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "broadcast_id": "123",
        "status": "started",
    }


def test_live_start_does_not_misclassify_non_boolean_result(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx",
        lambda ctx, account: FakeStringActionLiveClient(),
    )

    result = CliRunner().invoke(app, ["live", "start", "123"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "broadcast_id": "123",
        "success": None,
        "status": "start_result",
        "result": "failed",
    }


def test_live_end_normalizes_boolean_false_result(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx", lambda ctx, account: FakeLiveClient()
    )

    result = CliRunner().invoke(app, ["live", "end", "123"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {"broadcast_id": "123", "success": False, "status": "end_failed"}


def test_live_end_normalizes_boolean_true_result(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx", lambda ctx, account: FakeEndTrueLiveClient()
    )

    result = CliRunner().invoke(app, ["live", "end", "123"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {"broadcast_id": "123", "success": True, "status": "ended"}


def test_live_end_preserves_structured_result(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx",
        lambda ctx, account: FakeEndDictActionLiveClient(),
    )

    result = CliRunner().invoke(app, ["live", "end", "123"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "broadcast_id": "123",
        "status": "ended",
        "note": "already normalized",
    }


def test_live_end_fills_missing_broadcast_id_in_structured_result(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx",
        lambda ctx, account: FakeEndDictActionMissingBroadcastLiveClient(),
    )

    result = CliRunner().invoke(app, ["live", "end", "123"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "broadcast_id": "123",
        "status": "ended",
    }


def test_live_end_does_not_misclassify_non_boolean_result(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx",
        lambda ctx, account: FakeEndStringActionLiveClient(),
    )

    result = CliRunner().invoke(app, ["live", "end", "123"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "broadcast_id": "123",
        "success": None,
        "status": "end_result",
        "result": "error",
    }


def test_live_info_returns_json(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx", lambda ctx, account: FakeLiveClient()
    )

    result = CliRunner().invoke(app, ["live", "info", "123"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {"broadcast_id": "123", "status": "running"}


def test_live_comments_returns_json(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx", lambda ctx, account: FakeLiveClient()
    )

    result = CliRunner().invoke(app, ["live", "comments", "123"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == [{"pk": "comment1", "broadcast_id": "123"}]


def test_live_viewers_returns_json(monkeypatch):
    monkeypatch.setattr(
        "ig_cli.commands.live.get_client_from_ctx", lambda ctx, account: FakeLiveClient()
    )

    result = CliRunner().invoke(app, ["live", "viewers", "123"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == [{"pk": "viewer1", "broadcast_id": "123"}]
