import json
from typing import Any

import typer

from ig_cli.client import get_client_from_ctx
from ig_cli.introspection import get_method_signature, list_client_methods, summarize_cli_coverage
from ig_cli.output import print_error, print_json

app = typer.Typer(name="raw", help="Raw instagrapi method access", no_args_is_help=True)

CURATED_METHODS = {
    "account_info",
    "insights_account",
    "insights_media",
    "login",
    "media_create_livestream",
    "media_delete",
    "media_end_livestream",
    "media_get_livestream_comments",
    "media_get_livestream_info",
    "media_get_livestream_viewers",
    "media_info",
    "media_start_livestream",
    "photo_upload",
    "photo_upload_to_story",
    "story_viewers",
    "user_followers",
    "user_following",
    "user_info_by_username",
    "user_medias",
    "user_stories",
    "video_upload_to_story",
}

RAW_CALL_ALLOW_EXACT = {
    "share_info",
    "share_info_by_url",
}

# Conservative denylist for raw passthrough. Over-blocking is preferable to
# accidentally executing a write while the curated CLI surface is still growing.
RAW_CALL_DENY_PREFIXES = (
    "account_",
    "accounts_create",
    "album_configure",
    "album_upload",
    "bloks_",
    "challenge_",
    "change_",
    "clip_configure",
    "clip_upload",
    "close_friend_",
    "comment_",
    "create_",
    "delete_",
    "direct_",
    "disable_",
    "enable_",
    "hashtag_follow",
    "hashtag_unfollow",
    "highlight_",
    "igtv_configure",
    "igtv_upload",
    "login",
    "logout",
    "media_",
    "mute_",
    "notification_",
    "one_tap_app_login",
    "photo_configure",
    "photo_rupload",
    "photo_upload",
    "photo_upload_to_",
    "pre_login_",
    "remove_",
    "relogin",
    "report_",
    "reset_",
    "send_",
    "set_",
    "signup",
    "story_delete",
    "story_like",
    "story_unlike",
    "totp_",
    "two_factor",
    "unmute_",
    "user_block",
    "user_follow",
    "user_remove_follower",
    "user_unblock",
    "user_unfollow",
    "video_configure",
    "video_rupload",
    "video_upload",
    "video_upload_to_",
)


def parse_key_value_args(args: list[str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for item in args:
        if "=" not in item:
            raise ValueError(f"Invalid --arg '{item}'. Expected key=value.")
        key, raw_value = item.split("=", 1)
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            value = raw_value
        parsed[key] = value
    return parsed


def raw_call_is_allowed(method_name: str) -> bool:
    if method_name in RAW_CALL_ALLOW_EXACT:
        return True
    return not method_name.startswith(RAW_CALL_DENY_PREFIXES)


@app.command()
def methods() -> None:
    """List public instagrapi client methods."""
    print_json({"methods": list_client_methods()})


@app.command()
def coverage() -> None:
    """Report curated CLI coverage vs. public instagrapi Client methods."""
    print_json(summarize_cli_coverage(CURATED_METHODS))


@app.command()
def schema(method_name: str = typer.Argument(..., help="instagrapi Client method name")) -> None:
    """Show normalized parameter metadata for a client method."""
    try:
        signature = get_method_signature(method_name)
    except ValueError as exc:
        print_error(str(exc))
    print_json(signature)


@app.command()
def call(
    ctx: typer.Context,
    method_name: str = typer.Argument(..., help="instagrapi Client method name"),
    arg: list[str] = typer.Option([], "--arg", help="Repeatable key=value argument"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Invoke a read-only instagrapi client method by name."""
    if method_name not in list_client_methods():
        print_error(f"Unknown client method: {method_name}")
    if not raw_call_is_allowed(method_name):
        print_error("raw call currently supports read-only methods only")
    try:
        kwargs = parse_key_value_args(arg)
    except ValueError as exc:
        print_error(str(exc))
    client = get_client_from_ctx(ctx, account)
    attr = getattr(client, method_name, None)
    if attr is None or not callable(attr):
        print_error(f"Unknown client method: {method_name}")
    try:
        result = attr(**kwargs)
    except Exception as exc:
        print_error(str(exc))
    print_json(result)
