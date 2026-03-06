from pathlib import Path

import typer

from ig_cli.client import get_client_from_ctx
from ig_cli.output import print_json

app = typer.Typer(name="story", help="Story lookups and uploads", no_args_is_help=True)


@app.command(name="list")
def list_stories(
    ctx: typer.Context,
    user_id: str = typer.Argument(..., help="Instagram user id"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Fetch stories for a user id using the selected account."""
    client = get_client_from_ctx(ctx, account)
    print_json(client.user_stories(user_id))


@app.command()
def viewers(
    ctx: typer.Context,
    story_pk: str = typer.Argument(..., help="Instagram story primary key"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Fetch viewers for a story using the selected account."""
    client = get_client_from_ctx(ctx, account)
    print_json(client.story_viewers(story_pk))


@app.command()
def upload_photo(
    ctx: typer.Context,
    path: Path = typer.Argument(..., exists=True, dir_okay=False, help="Path to a photo file"),
    caption: str = typer.Option("", "--caption", help="Caption text"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Upload a story photo using the selected account."""
    client = get_client_from_ctx(ctx, account)
    print_json(client.photo_upload_to_story(path, caption=caption))


@app.command()
def upload_video(
    ctx: typer.Context,
    path: Path = typer.Argument(..., exists=True, dir_okay=False, help="Path to a video file"),
    caption: str = typer.Option("", "--caption", help="Caption text"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Upload a story video using the selected account."""
    client = get_client_from_ctx(ctx, account)
    print_json(client.video_upload_to_story(path, caption=caption))
