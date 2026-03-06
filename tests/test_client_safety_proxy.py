import json

import pytest
import typer
from instagrapi.exceptions import ChallengeRequired, LoginRequired

from ig_cli.client import SafeClientOptions, SafeClientProxy, _method_kind


class DummyClient:
    def user_info_by_username(self, username: str):
        return {"username": username}

    def media_delete(self, media_id: str):
        return {"deleted": media_id}


class ChallengeClient:
    def user_info_by_username(self, username: str):
        raise ChallengeRequired("challenge_required")


class LoginRequiredClient:
    def user_info_by_username(self, username: str):
        raise LoginRequired("login_required")


class DummyExecutor:
    def __init__(self) -> None:
        self.calls = []

    def execute(self, meta, fn, **kwargs):
        self.calls.append((meta, kwargs))
        return fn()


def test_safe_proxy_wraps_read_method():
    executor = DummyExecutor()
    proxy = SafeClientProxy(
        account="testacct",
        client=DummyClient(),
        executor=executor,  # type: ignore[arg-type]
        options=SafeClientOptions(),
    )

    result = proxy.user_info_by_username("alice")
    assert result["username"] == "alice"
    meta, kwargs = executor.calls[-1]
    assert meta.kind == "read"
    assert meta.scope == "user_info_by_username"
    assert meta.high_risk is False
    assert kwargs["yes"] is False


def test_safe_proxy_marks_high_risk_write():
    executor = DummyExecutor()
    proxy = SafeClientProxy(
        account="testacct",
        client=DummyClient(),
        executor=executor,  # type: ignore[arg-type]
        options=SafeClientOptions(yes=True, confirm="media.delete:testacct"),
    )

    result = proxy.media_delete("123")
    assert result["deleted"] == "123"
    meta, kwargs = executor.calls[-1]
    assert meta.kind == "write"
    assert meta.high_risk is True
    assert kwargs["yes"] is True
    assert kwargs["confirm_token"] == "media.delete:testacct"


def test_safe_proxy_unsafe_bypasses_executor():
    executor = DummyExecutor()
    proxy = SafeClientProxy(
        account="testacct",
        client=DummyClient(),
        executor=executor,  # type: ignore[arg-type]
        options=SafeClientOptions(unsafe=True),
    )

    result = proxy.media_delete("123")
    assert result["deleted"] == "123"
    assert executor.calls == []


@pytest.mark.parametrize(
    ("client_factory", "expected_fragment"),
    [
        (ChallengeClient, "checkpoint required"),
        (LoginRequiredClient, "session for 'testacct' is no longer valid"),
    ],
)
def test_safe_proxy_surfaces_auth_failures_as_json_errors(
    client_factory, expected_fragment, capsys
):
    executor = DummyExecutor()
    proxy = SafeClientProxy(
        account="testacct",
        client=client_factory(),
        executor=executor,  # type: ignore[arg-type]
        options=SafeClientOptions(),
    )

    with pytest.raises(typer.Exit):
        proxy.user_info_by_username("alice")

    payload = json.loads(capsys.readouterr().err)
    assert expected_fragment in payload["error"].lower()


@pytest.mark.parametrize(
    ("method_name", "expected_kind"),
    [
        ("change_password", "auth"),
        ("logout", "auth"),
        ("send_confirm_email", "auth"),
        ("totp_enable", "auth"),
        ("accounts_create", "write"),
        ("create_note", "write"),
        ("direct_thread_mute", "write"),
        ("highlight_remove_stories", "write"),
        ("set_locale", "write"),
        ("share_info", "read"),
        ("notification_likes", "read"),
        ("search_followers", "read"),
    ],
)
def test_method_kind_covers_representative_instagrapi_methods(method_name, expected_kind):
    assert _method_kind(method_name) == expected_kind
