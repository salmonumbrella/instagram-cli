import typer
from instagrapi import Client
from instagrapi.exceptions import TwoFactorRequired

from ig_cli.client import (
    AUTH_CHALLENGE_EXCEPTIONS,
    AUTH_SESSION_EXCEPTIONS,
    HANDLED_AUTH_EXCEPTIONS,
    configure_client,
    ensure_login_succeeded,
    handle_client_auth_error,
    get_raw_client,
)
from ig_cli.config import Config
from ig_cli.helptext import load_help_text
from ig_cli.output import print_error, print_json
from ig_cli.runtime import get_runtime_options

app = typer.Typer(name="auth", help=load_help_text("auth_help.txt"), no_args_is_help=True)


def _session_status(cfg: Config, alias: str) -> dict[str, object]:
    session_path = cfg.session_path(alias)
    if not session_path.exists():
        return {"alias": alias, "status": "no_session", "path": session_path}
    try:
        session_data = cfg.load_session(alias)
    except (PermissionError, ValueError) as exc:
        print_error(str(exc))
        raise RuntimeError("unreachable") from exc
    if not isinstance(session_data, dict):
        print_error(f"Session file {session_path} must contain a JSON/TOML object.")
        raise RuntimeError("unreachable")
    return {
        "alias": alias,
        "status": "session_exists",
        "path": session_path,
        "has_cookies": "cookies" in session_data,
    }


def _account_info_or_exit(alias: str, client: Client):
    try:
        return client.account_info()
    except AUTH_CHALLENGE_EXCEPTIONS as exc:
        handle_client_auth_error(alias, exc)
        raise
    except AUTH_SESSION_EXCEPTIONS as exc:
        handle_client_auth_error(alias, exc)
        raise


@app.command()
def login(
    alias: str = typer.Option(..., help="Account alias (e.g. 'test')"),
    username: str = typer.Option(..., prompt=True, help="Instagram username"),
    password: str = typer.Option(..., prompt=True, hide_input=True, help="Instagram password"),
    verification_code: str = typer.Option(
        "",
        "--code",
        help="6-digit 2FA code. If omitted, you will be prompted when required.",
    ),
    make_default: bool = typer.Option(
        False,
        "--default",
        help="Set this alias as the default account after successful login.",
    ),
) -> None:
    """Interactive login. Saves the instagrapi session for future commands."""
    cfg = Config()
    cl = Client()
    try:
        existing_session = cfg.load_session(alias)
    except (PermissionError, ValueError):
        existing_session = None
    try:
        configure_client(alias, cl, cfg, session=existing_session)
    except (RuntimeError, ValueError) as exc:
        print_error(str(exc))

    try:
        ok = cl.login(username, password, verification_code=verification_code)
        ensure_login_succeeded(alias, bool(ok), interactive=True)
    except TwoFactorRequired:
        prompted_code = typer.prompt("Instagram 2FA code", prompt_suffix=": ").strip()
        if not prompted_code:
            print_error("2FA code is required to complete login.")
        try:
            ok = cl.login(username, password, verification_code=prompted_code)
            ensure_login_succeeded(alias, bool(ok), interactive=True)
        except HANDLED_AUTH_EXCEPTIONS as exc:
            handle_client_auth_error(alias, exc)
        except typer.Exit:
            raise
        except Exception as exc:
            print_error(str(exc))
    except HANDLED_AUTH_EXCEPTIONS as exc:
        handle_client_auth_error(alias, exc)
    except typer.Exit:
        raise
    except Exception as exc:
        print_error(str(exc))

    cfg.save_session(alias, cl.get_settings())
    if make_default:
        cfg.set_default_account(alias)
    print_json(
        {
            "status": "logged_in",
            "alias": alias,
            "username": username,
            "default": make_default,
            "session_path": cfg.session_path(alias),
        }
    )


@app.command()
def logout(alias: str = typer.Option(..., help="Account alias to log out")) -> None:
    """Remove the saved session for an account."""
    cfg = Config()
    session_path = cfg.session_path(alias)
    removed = False
    if session_path.exists():
        session_path.unlink()
        removed = True
    print_json({"status": "logged_out", "alias": alias, "removed": removed})


@app.command()
def default(alias: str = typer.Argument(..., help="Account alias to set as default")) -> None:
    """Set the default account alias."""
    cfg = Config()
    cfg.set_default_account(alias)
    print_json({"status": "default_set", "alias": alias})


@app.command(name="list")
def list_accounts() -> None:
    """List all saved account aliases."""
    cfg = Config()
    print_json({"accounts": cfg.list_accounts(), "default": cfg.get_default_account()})


@app.command()
def session(alias: str = typer.Option(..., help="Account alias")) -> None:
    """Show session status for an account."""
    cfg = Config()
    print_json(_session_status(cfg, alias))


@app.command()
def whoami(
    ctx: typer.Context,
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Show the authenticated identity for the selected account alias."""
    runtime = get_runtime_options(ctx)
    alias, client = get_raw_client(account or runtime.account)
    me = _account_info_or_exit(alias, client)
    print_json(
        {
            "alias": alias,
            "username": me.username,
            "pk": me.pk,
            "full_name": me.full_name,
            "is_private": me.is_private,
            "is_verified": me.is_verified,
        }
    )


@app.command()
def validate(
    ctx: typer.Context,
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
) -> None:
    """Deliberately validate the selected account/session."""
    runtime = get_runtime_options(ctx)
    alias, client = get_raw_client(account or runtime.account)
    me = _account_info_or_exit(alias, client)
    print_json(
        {
            "alias": alias,
            "status": "valid",
            "username": me.username,
            "pk": me.pk,
        }
    )
