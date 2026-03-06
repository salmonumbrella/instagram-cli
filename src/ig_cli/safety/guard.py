import sys
from typing import Callable

import typer

from ig_cli.safety.errors import WriteGuardError
from ig_cli.safety.policy import WriteGuardPolicy


class WriteGuard:
    def __init__(self, policy: WriteGuardPolicy) -> None:
        self.policy = policy

    def enforce(
        self,
        account: str,
        scope: str,
        kind: str,
        high_risk: bool,
        yes: bool,
        confirm_token: str | None,
        stdin_isatty: bool | None = None,
        prompt_fn: Callable[[str, bool], bool] | None = None,
    ) -> None:
        if kind != "write" or not self.policy.require_confirmation_for_write:
            return

        if high_risk and self.policy.require_typed_confirm_for_high_risk:
            expected = f"{scope}:{account}"
            if confirm_token != expected:
                raise WriteGuardError(f"High-risk write requires --confirm '{expected}'.")
            return

        if yes and self.policy.allow_yes_flag:
            return

        interactive = stdin_isatty if stdin_isatty is not None else sys.stdin.isatty()
        if not interactive and self.policy.fail_if_non_tty_without_yes:
            raise WriteGuardError("Write action requires --yes in non-interactive mode.")

        if prompt_fn is None:
            prompt_fn = typer.confirm
        prompt = f"Proceed with write action '{scope}' for account '{account}'?"
        if not prompt_fn(prompt, False):
            raise WriteGuardError("Write action cancelled.")
