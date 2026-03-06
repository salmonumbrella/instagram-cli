from pathlib import Path

import typer

from ig_cli.client import get_client_from_ctx
from ig_cli.output import print_json

app = typer.Typer(name="media", help="Media lookups", no_args_is_help=True)


@app.command()
def info(
    ctx: typer.Context,
    media_pk: str = typer.Argument(..., help="Instagram media primary key"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Fetch media details for a media primary key using the selected account."""
    client = get_client_from_ctx(ctx, account)
    print_json(client.media_info(media_pk))


@app.command()
def user(
    ctx: typer.Context,
    user_id: str = typer.Argument(..., help="Instagram user id"),
    amount: int = typer.Option(0, "--amount", min=0, help="Max medias to fetch"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Fetch medias for a user id using the selected account."""
    client = get_client_from_ctx(ctx, account)
    print_json(client.user_medias(user_id, amount=amount))


@app.command()
def upload_photo(
    ctx: typer.Context,
    path: Path = typer.Argument(..., exists=True, dir_okay=False, help="Path to a photo file"),
    caption: str = typer.Option("", "--caption", help="Caption text"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Upload a photo using the selected account."""
    client = get_client_from_ctx(ctx, account)
    print_json(client.photo_upload(path, caption=caption))


@app.command(name="delete")
def delete_media(
    ctx: typer.Context,
    media_pk: str = typer.Argument(..., help="Instagram media primary key"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Delete a media item using the selected account."""
    client = get_client_from_ctx(ctx, account)
    result = client.media_delete(media_pk)
    print_json({"media_pk": media_pk, "deleted": bool(result), "result": result})
