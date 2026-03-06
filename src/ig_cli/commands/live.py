from urllib.parse import urlsplit

import typer

from ig_cli.client import get_client_from_ctx
from ig_cli.output import print_json

app = typer.Typer(name="live", help="Instagram Live workflows", no_args_is_help=True)


def _split_upload_url(upload_url: str, broadcast_id: object | None = None) -> tuple[str, str]:
    parts = urlsplit(upload_url)
    if not parts.scheme or not parts.netloc:
        return upload_url, ""
    path = parts.path or ""
    if path and not path.endswith("/"):
        stream_server_path, separator, stream_key = path.rpartition("/")
        if separator and stream_key and stream_server_path:
            stream_server = f"{parts.scheme}://{parts.netloc}{stream_server_path}/"
            if parts.query:
                stream_key = f"{stream_key}?{parts.query}"
            return stream_server, stream_key
    return upload_url, ""


def _normalize_create_payload(result: object) -> object:
    if not isinstance(result, dict):
        return result
    payload = dict(result)
    broadcast_id = payload.get("broadcast_id")
    stream_server = payload.get("stream_server")
    stream_key = payload.get("stream_key")
    if isinstance(stream_server, str) and isinstance(stream_key, str):
        return payload
    upload_url = payload.get("upload_url")
    if not isinstance(upload_url, str):
        return payload
    derived_stream_server, derived_stream_key = _split_upload_url(upload_url, broadcast_id)
    if not isinstance(stream_server, str):
        payload["stream_server"] = derived_stream_server
    if not isinstance(stream_key, str):
        payload["stream_key"] = derived_stream_key
    return payload


def _normalize_action_payload(action: str, broadcast_id: str, result: object) -> dict[str, object]:
    if isinstance(result, dict):
        payload = dict(result)
        if payload.get("broadcast_id") in (None, ""):
            payload["broadcast_id"] = broadcast_id
        return payload
    if isinstance(result, bool):
        success = result
        status = f"{action}ed" if success else f"{action}_failed"
        return {
            "broadcast_id": broadcast_id,
            "success": success,
            "status": status,
        }
    return {
        "broadcast_id": broadcast_id,
        "success": None,
        "status": f"{action}_result",
        "result": result,
    }


@app.command()
def create(
    ctx: typer.Context,
    title: str = typer.Option("Instagram Live", "--title", help="Broadcast title"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Create a live broadcast and return stream connection details."""
    client = get_client_from_ctx(ctx, account)
    print_json(_normalize_create_payload(client.media_create_livestream(title=title)))


@app.command()
def start(
    ctx: typer.Context,
    broadcast_id: str = typer.Argument(..., help="Instagram broadcast id"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Start a prepared live broadcast."""
    client = get_client_from_ctx(ctx, account)
    print_json(
        _normalize_action_payload(
            "start", broadcast_id, client.media_start_livestream(broadcast_id)
        )
    )


@app.command()
def end(
    ctx: typer.Context,
    broadcast_id: str = typer.Argument(..., help="Instagram broadcast id"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """End a live broadcast."""
    client = get_client_from_ctx(ctx, account)
    print_json(
        _normalize_action_payload("end", broadcast_id, client.media_end_livestream(broadcast_id))
    )


@app.command()
def info(
    ctx: typer.Context,
    broadcast_id: str = typer.Argument(..., help="Instagram broadcast id"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Fetch live broadcast metadata."""
    client = get_client_from_ctx(ctx, account)
    print_json(client.media_get_livestream_info(broadcast_id))


@app.command()
def comments(
    ctx: typer.Context,
    broadcast_id: str = typer.Argument(..., help="Instagram broadcast id"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Fetch comments for a live broadcast."""
    client = get_client_from_ctx(ctx, account)
    print_json(client.media_get_livestream_comments(broadcast_id))


@app.command()
def viewers(
    ctx: typer.Context,
    broadcast_id: str = typer.Argument(..., help="Instagram broadcast id"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Fetch viewers for a live broadcast."""
    client = get_client_from_ctx(ctx, account)
    print_json(client.media_get_livestream_viewers(broadcast_id))
