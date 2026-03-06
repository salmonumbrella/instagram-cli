import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable

import typer
from instagrapi import Client
from instagrapi.exceptions import (
    BadPassword,
    ChallengeRequired,
    ChallengeRedirection,
    ChallengeSelfieCaptcha,
    ChallengeUnknownStep,
    ClientForbiddenError,
    ClientLoginRequired,
    ClientUnauthorizedError,
    LoginRequired,
    TwoFactorRequired,
)

from ig_cli.config import Config
from ig_cli.output import print_error
from ig_cli.runtime import get_runtime_options
from ig_cli.safety import OperationMeta, SafetyExecutor, build_safety_executor


AUTH_METHOD_PREFIXES = (
    "login",
    "logout",
    "relogin",
    "two_factor",
    "challenge",
    "bloks_change_password",
    "change_password",
    "check_confirmation_code",
    "one_tap_app_login",
    "pre_login_flow",
    "reset_password",
    "send_confirm_",
    "send_verify_",
    "signup",
    "totp_",
)

WRITE_METHOD_PREFIXES = (
    "accounts_create",
    "album_configure",
    "media_create_livestream",
    "media_start_livestream",
    "media_end_livestream",
    "media_configure",
    "media_pin",
    "media_unpin",
    "photo_upload",
    "photo_configure",
    "photo_rupload",
    "video_upload",
    "video_configure",
    "video_rupload",
    "clip_upload",
    "clip_configure",
    "album_upload",
    "igtv_upload",
    "igtv_configure",
    "photo_upload_to_story",
    "video_upload_to_story",
    "media_delete",
    "media_edit",
    "media_archive",
    "media_unarchive",
    "media_like",
    "media_unlike",
    "media_save",
    "media_unsave",
    "story_delete",
    "story_like",
    "story_unlike",
    "create_",
    "delete_",
    "remove_",
    "report_",
    "direct_send",
    "direct_answer",
    "direct_message_delete",
    "direct_pending_approve",
    "direct_profile_share",
    "direct_story_share",
    "direct_thread_",
    "comment_",
    "close_friend_",
    "mute_",
    "unmute_",
    "enable_",
    "disable_",
    "user_follow",
    "user_unfollow",
    "user_block",
    "user_unblock",
    "user_remove_follower",
    "hashtag_follow",
    "hashtag_unfollow",
    "account_",
    "highlight_create",
    "highlight_delete",
    "highlight_change_title",
    "highlight_change_cover",
    "highlight_edit",
    "highlight_add_",
    "highlight_remove_",
    "set_",
)

HIGH_RISK_MARKERS = (
    "delete",
    "remove",
    "block",
    "unfollow",
    "archive",
    "set_private",
    "end_livestream",
    "account_edit",
    "change_picture",
    "change_password",
    "reset_password",
)

AUTH_CHALLENGE_EXCEPTIONS = (
    ChallengeRequired,
    ChallengeUnknownStep,
    ChallengeRedirection,
    ChallengeSelfieCaptcha,
)

AUTH_SESSION_EXCEPTIONS = (
    LoginRequired,
    ClientLoginRequired,
    ClientUnauthorizedError,
    ClientForbiddenError,
)

HANDLED_AUTH_EXCEPTIONS = AUTH_CHALLENGE_EXCEPTIONS + AUTH_SESSION_EXCEPTIONS + (BadPassword,)


def resolve_account(account: str | None, cfg: Config | None = None) -> str:
    if account:
        return account
    config = cfg or Config()
    default = config.get_default_account()
    if default:
        return default
    sys.stderr.write(
        json.dumps(
            {"error": ("No account specified and no default set. " + config.default_account_hint())}
        )
        + "\n"
    )
    raise typer.Exit(code=1)


def _op_read(op_ref: str) -> str:
    try:
        result = subprocess.run(["op", "read", op_ref], capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("1Password CLI `op` is not installed or not on PATH.") from exc
    if result.returncode == 0:
        return result.stdout.strip()
    stderr = result.stderr.strip() or "op read failed"
    raise RuntimeError(f"Failed to resolve secret from {op_ref}: {stderr}")


def _account_env_suffix(alias: str) -> str:
    return re.sub(r"[^A-Z0-9]", "_", alias.upper())


def _env_value(alias: str, name: str) -> str | None:
    alias_key = f"IG_CLI_{name}_{_account_env_suffix(alias)}"
    if value := os.environ.get(alias_key):
        return value
    return os.environ.get(f"IG_CLI_{name}")


def _runtime_setting(
    alias: str, config: Config, creds: dict[str, Any] | None, key: str
) -> str | None:
    env_name = key.upper()
    if value := _env_value(alias, env_name):
        return value
    if creds and isinstance(creds.get(key), str):
        return creds[key]
    if creds and isinstance(creds.get(f"{key}_op_ref"), str):
        return _op_read(creds[f"{key}_op_ref"])
    account_settings = config.account_settings(alias)
    if isinstance(account_settings.get(key), str):
        return account_settings[key]
    if isinstance(account_settings.get(f"{key}_op_ref"), str):
        return _op_read(account_settings[f"{key}_op_ref"])
    runtime_settings = config.global_runtime_settings()
    if isinstance(runtime_settings.get(key), str):
        return runtime_settings[key]
    if isinstance(runtime_settings.get(f"{key}_op_ref"), str):
        return _op_read(runtime_settings[f"{key}_op_ref"])
    return None


def _resolve_password(creds: dict[str, str]) -> str | None:
    if "password" in creds:
        return creds["password"]
    op_ref = creds.get("password_op_ref")
    if not op_ref:
        return None
    return _op_read(op_ref)


def _resolve_totp(creds: dict[str, str]) -> str | None:
    op_ref = creds.get("totp_op_ref")
    if not op_ref:
        return None
    return _op_read(op_ref)


def _method_kind(method_name: str) -> str:
    if method_name.startswith(AUTH_METHOD_PREFIXES):
        return "auth"
    if method_name.startswith(WRITE_METHOD_PREFIXES):
        return "write"
    return "read"


def _method_high_risk(method_name: str) -> bool:
    return any(marker in method_name for marker in HIGH_RISK_MARKERS)


def _auth_error_message(alias: str, exc: Exception) -> str:
    if isinstance(exc, AUTH_CHALLENGE_EXCEPTIONS):
        return (
            f"Instagram checkpoint required for '{alias}'. "
            "Open Instagram and complete the security challenge, then retry."
        )
    if isinstance(exc, TwoFactorRequired):
        return (
            f"Stored credentials for '{alias}' require interactive 2FA. "
            f"Run `ig auth login --alias {alias}`."
        )
    if isinstance(exc, AUTH_SESSION_EXCEPTIONS):
        return (
            f"Instagram session for '{alias}' is no longer valid. "
            "Log in again or refresh credentials."
        )
    if isinstance(exc, BadPassword):
        return f"Stored credentials for '{alias}' were rejected by Instagram."
    return str(exc)


def handle_client_auth_error(alias: str, exc: Exception) -> None:
    print_error(_auth_error_message(alias, exc))


def ensure_login_succeeded(alias: str, ok: bool, *, interactive: bool = False) -> None:
    if ok:
        return
    if interactive:
        print_error(f"Instagram login failed for '{alias}'. Check credentials or 2FA and retry.")
    else:
        print_error(f"Stored credentials for '{alias}' did not produce a valid Instagram login.")


def _require_mapping(alias: str, kind: str, value: object, path: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    print_error(f"{kind} file {path} for '{alias}' must contain a JSON/TOML object.")
    raise RuntimeError("unreachable")


def _run_handler_command(command: str, extra_env: dict[str, str]) -> str:
    env = {**os.environ, **extra_env}
    result = subprocess.run(shlex.split(command), capture_output=True, text=True, env=env)
    if result.returncode != 0:
        stderr = result.stderr.strip() or "handler command failed"
        raise RuntimeError(f"Handler command failed: {stderr}")
    return result.stdout.strip()


def _challenge_code_handler_from_command(command: str) -> Callable[[str, object], str]:
    def _handler(username: str, choice=None) -> str:
        code = _run_handler_command(
            command,
            {
                "IG_USERNAME": username,
                "IG_CHOICE": "" if choice is None else str(choice),
            },
        )
        if not code:
            raise RuntimeError("Challenge code handler returned an empty code.")
        return code

    return _handler


def _change_password_handler_from_command(command: str) -> Callable[[str], str]:
    def _handler(username: str) -> str:
        password = _run_handler_command(command, {"IG_USERNAME": username})
        if not password:
            raise RuntimeError("Change-password handler returned an empty password.")
        return password

    return _handler


def _handle_exception(alias: str) -> Callable[[Client, Exception], None]:
    def _handler(client: Client, exc: Exception) -> None:
        if isinstance(exc, ChallengeRequired):
            challenge_handler = getattr(client, "challenge_code_handler", None)
            password_handler = getattr(client, "change_password_handler", None)
            if challenge_handler or password_handler:
                client.challenge_resolve(client.last_json)
                return
            raise exc
        raise exc

    return _handler


def configure_client(
    alias: str,
    client: Client,
    config: Config,
    *,
    creds: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
) -> Client:
    if isinstance(session, dict) and isinstance(session.get("uuids"), dict):
        client.set_uuids(session["uuids"])

    if proxy := _runtime_setting(alias, config, creds, "proxy"):
        client.set_proxy(proxy)

    if command := _runtime_setting(alias, config, creds, "challenge_code_cmd"):
        client.challenge_code_handler = _challenge_code_handler_from_command(command)

    if command := _runtime_setting(alias, config, creds, "change_password_cmd"):
        client.change_password_handler = _change_password_handler_from_command(command)

    client.handle_exception = _handle_exception(alias)
    return client


@dataclass
class SafeClientOptions:
    yes: bool = False
    confirm: str | None = None
    no_wait: bool = False
    unsafe: bool = False


class SafeClientProxy:
    def __init__(
        self,
        account: str,
        client: Client,
        executor: SafetyExecutor,
        options: SafeClientOptions | None = None,
    ) -> None:
        self._account = account
        self._client = client
        self._executor = executor
        self._options = options or SafeClientOptions()

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._client, name)
        if not callable(attr) or name.startswith("_") or self._options.unsafe:
            return attr

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            kind = _method_kind(name)
            meta = OperationMeta(
                account=self._account,
                scope=name,
                kind=kind,  # type: ignore[arg-type]
                high_risk=_method_high_risk(name),
            )
            try:
                return self._executor.execute(
                    meta,
                    lambda: attr(*args, **kwargs),
                    yes=self._options.yes,
                    confirm_token=self._options.confirm,
                    no_wait=self._options.no_wait,
                )
            except AUTH_CHALLENGE_EXCEPTIONS as exc:
                handle_client_auth_error(self._account, exc)
                raise
            except AUTH_SESSION_EXCEPTIONS as exc:
                handle_client_auth_error(self._account, exc)
                raise

        return wrapped


def get_raw_client(account: str | None = None, cfg: Config | None = None) -> tuple[str, Client]:
    config = cfg or Config()
    alias = resolve_account(account, config)
    cl = Client()
    session_path = config.session_path(alias)
    creds = None

    if session_path.exists():
        try:
            session = config.load_session(alias)
        except (PermissionError, ValueError) as exc:
            print_error(str(exc))
            raise RuntimeError("unreachable") from exc
        try:
            creds = config.load_credentials(alias)
        except (PermissionError, ValueError) as exc:
            print_error(str(exc))
            raise RuntimeError("unreachable") from exc
        try:
            configure_client(alias, cl, config, creds=creds, session=session)
        except (RuntimeError, ValueError) as exc:
            print_error(str(exc))
            raise RuntimeError("unreachable") from exc
        cl.set_settings(_require_mapping(alias, "Session", session, session_path))
        return alias, cl

    try:
        creds = config.load_credentials(alias)
    except (PermissionError, ValueError) as exc:
        print_error(str(exc))
        raise RuntimeError("unreachable") from exc
    if creds:
        credential_path = next(
            (path for path in config.credential_paths(alias) if path.exists()), "<unknown>"
        )
        creds = _require_mapping(alias, "Credential", creds, credential_path)
        username = creds.get("username")
        try:
            password = _resolve_password(creds)
            totp_code = _resolve_totp(creds)
            configure_client(alias, cl, config, creds=creds)
        except RuntimeError as exc:
            print_error(str(exc))
            raise RuntimeError("unreachable") from exc
        except ValueError as exc:
            print_error(str(exc))
            raise RuntimeError("unreachable") from exc
        if username and password:
            try:
                ok = cl.login(username, password, verification_code=totp_code or "")
            except AUTH_CHALLENGE_EXCEPTIONS as exc:
                handle_client_auth_error(alias, exc)
                raise
            except AUTH_SESSION_EXCEPTIONS as exc:
                handle_client_auth_error(alias, exc)
                raise
            except TwoFactorRequired as exc:
                handle_client_auth_error(alias, exc)
                raise
            except BadPassword as exc:
                handle_client_auth_error(alias, exc)
                raise
            ensure_login_succeeded(alias, bool(ok))
            config.save_session(alias, cl.get_settings())
            return alias, cl

    sys.stderr.write(
        json.dumps(
            {
                "error": (
                    f"No valid session or credentials for '{alias}'. "
                    + config.account_material_hint(alias)
                )
            }
        )
        + "\n"
    )
    raise typer.Exit(code=1)


def get_client(
    account: str | None = None,
    *,
    yes: bool = False,
    confirm: str | None = None,
    no_wait: bool = False,
    unsafe: bool = False,
    cfg: Config | None = None,
) -> SafeClientProxy | Client:
    config = cfg or Config()
    alias, raw_client = get_raw_client(account, cfg=config)
    if unsafe:
        return raw_client
    try:
        executor = build_safety_executor(config=config)
    except ValueError as exc:
        print_error(str(exc))
        raise RuntimeError("unreachable") from exc
    options = SafeClientOptions(yes=yes, confirm=confirm, no_wait=no_wait, unsafe=unsafe)
    return SafeClientProxy(alias, raw_client, executor, options=options)


def get_client_from_ctx(ctx: typer.Context, account: str | None = None) -> SafeClientProxy | Client:
    runtime = get_runtime_options(ctx)
    return get_client(
        account=account or runtime.account,
        yes=runtime.yes,
        confirm=runtime.confirm,
        no_wait=runtime.no_wait,
        unsafe=runtime.unsafe,
    )
