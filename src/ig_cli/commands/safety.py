import typer

from ig_cli.config import Config
from ig_cli.output import print_error, print_json
from ig_cli.runtime import get_runtime_options
from ig_cli.safety import build_safety_executor

app = typer.Typer(name="safety", help="Safety controls and status", no_args_is_help=True)


def _resolve_account(cfg: Config, account: str | None) -> str:
    if account:
        return account
    default = cfg.get_default_account()
    if default:
        return default
    print_error(f"No account specified and no default set. {cfg.default_account_hint()}")
    raise AssertionError("unreachable")


def _build_executor(cfg: Config):
    try:
        return build_safety_executor(cfg)
    except ValueError as exc:
        print_error(str(exc))


@app.command()
def status(
    ctx: typer.Context,
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
):
    """Show current safety state for an account."""
    cfg = Config()
    runtime = get_runtime_options(ctx)
    alias = _resolve_account(cfg, account or runtime.account)
    executor = _build_executor(cfg)
    print_json(executor.snapshot(alias))


@app.command()
def reset(
    ctx: typer.Context,
    account: str | None = typer.Option(None, "--account", "-a", help="Account alias"),
):
    """Reset circuit-breaker and rate-limit state for an account."""
    cfg = Config()
    runtime = get_runtime_options(ctx)
    alias = _resolve_account(cfg, account or runtime.account)
    executor = _build_executor(cfg)
    executor.store.reset_account(alias)
    print_json({"status": "safety_state_reset", "account": alias})
