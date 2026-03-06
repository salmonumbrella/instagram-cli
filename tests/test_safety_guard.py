import pytest

from ig_cli.safety.errors import WriteGuardError
from ig_cli.safety.guard import WriteGuard
from ig_cli.safety.policy import WriteGuardPolicy


def test_write_guard_requires_yes_in_non_tty():
    guard = WriteGuard(WriteGuardPolicy())
    with pytest.raises(WriteGuardError):
        guard.enforce(
            account="testacct",
            scope="media.upload_photo",
            kind="write",
            high_risk=False,
            yes=False,
            confirm_token=None,
            stdin_isatty=False,
            prompt_fn=lambda _msg, _default: False,
        )


def test_high_risk_requires_typed_confirm():
    guard = WriteGuard(WriteGuardPolicy())
    with pytest.raises(WriteGuardError):
        guard.enforce(
            account="testacct",
            scope="media.delete",
            kind="write",
            high_risk=True,
            yes=True,
            confirm_token=None,
            stdin_isatty=False,
        )

    guard.enforce(
        account="testacct",
        scope="media.delete",
        kind="write",
        high_risk=True,
        yes=True,
        confirm_token="media.delete:testacct",
        stdin_isatty=False,
    )
