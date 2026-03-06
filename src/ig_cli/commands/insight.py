import typer

from ig_cli.client import get_client_from_ctx
from ig_cli.output import print_json

app = typer.Typer(name="insight", help="Instagram insights", no_args_is_help=True)


@app.command()
def account(
    ctx: typer.Context,
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Fetch account-level insights for the selected account."""
    client = get_client_from_ctx(ctx, account)
    print_json(client.insights_account())


@app.command()
def media(
    ctx: typer.Context,
    media_pk: int = typer.Argument(..., help="Instagram media primary key"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Fetch insights for a media item."""
    client = get_client_from_ctx(ctx, account)
    print_json(client.insights_media(media_pk))
