import json

from typer.testing import CliRunner

from ig_cli.main import app
from ig_cli.runtime import get_runtime_options


class FakeInsightClient:
    def insights_account(self):
        return {"impressions": 10, "reach": 8}

    def insights_media(self, media_pk: int):
        return {"media_pk": media_pk, "reach": 20}


def test_insight_account_returns_json(monkeypatch):
    forwarded = {}

    def fake_get_client_from_ctx(ctx, account):
        forwarded["account"] = account
        forwarded["runtime_account"] = get_runtime_options(ctx).account
        return FakeInsightClient()

    monkeypatch.setattr("ig_cli.commands.insight.get_client_from_ctx", fake_get_client_from_ctx)

    result = CliRunner().invoke(app, ["--account", "panpan_test", "insight", "account"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert forwarded["account"] is None
    assert forwarded["runtime_account"] == "panpan_test"
    assert payload == {"impressions": 10, "reach": 8}


def test_insight_media_returns_json(monkeypatch):
    forwarded = {}

    def fake_get_client_from_ctx(ctx, account):
        forwarded["account"] = account
        return FakeInsightClient()

    monkeypatch.setattr("ig_cli.commands.insight.get_client_from_ctx", fake_get_client_from_ctx)

    result = CliRunner().invoke(app, ["insight", "media", "123", "--account", "panpan_test"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert forwarded["account"] == "panpan_test"
    assert payload == {"media_pk": 123, "reach": 20}
