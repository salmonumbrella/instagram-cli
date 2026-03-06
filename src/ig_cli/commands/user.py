import typer

from ig_cli.client import get_client_from_ctx
from ig_cli.output import print_json

app = typer.Typer(name="user", help="User lookups", no_args_is_help=True)


@app.command()
def info(
    ctx: typer.Context,
    username: str = typer.Argument(..., help="Instagram username"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Fetch public/profile info for a username using the selected account."""
    client = get_client_from_ctx(ctx, account)
    print_json(client.user_info_by_username(username))


@app.command()
def followers(
    ctx: typer.Context,
    user_id: str = typer.Argument(..., help="Instagram user id"),
    amount: int = typer.Option(0, "--amount", min=0, help="Max followers to fetch"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Fetch followers for a user id using the selected account."""
    client = get_client_from_ctx(ctx, account)
    print_json(client.user_followers(user_id, amount=amount))


@app.command()
def following(
    ctx: typer.Context,
    user_id: str = typer.Argument(..., help="Instagram user id"),
    amount: int = typer.Option(0, "--amount", min=0, help="Max following accounts to fetch"),
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Fetch following accounts for a user id using the selected account."""
    client = get_client_from_ctx(ctx, account)
    print_json(client.user_following(user_id, amount=amount))
