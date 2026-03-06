import sys

import typer
from typer.core import TyperGroup

from ig_cli.commands import auth, insight, live, media, raw, safety, story, user
from ig_cli.config import Config
from ig_cli.helptext import load_help_text
from ig_cli.runtime import RuntimeOptions, set_runtime_options


class AccountAliasTyperGroup(TyperGroup):
    def parse_args(self, ctx, args):
        return super().parse_args(ctx, rewrite_account_alias_args(args))


app = typer.Typer(
    name="ig",
    help=load_help_text("help.txt"),
    no_args_is_help=True,
    cls=AccountAliasTyperGroup,
)

TOP_LEVEL_COMMANDS = {
    "safety": safety.app,
    "auth": auth.app,
    "user": user.app,
    "media": media.app,
    "story": story.app,
    "live": live.app,
    "insight": insight.app,
    "raw": raw.app,
}

for command in TOP_LEVEL_COMMANDS.values():
    app.add_typer(command)

ROOT_COMMANDS = set(TOP_LEVEL_COMMANDS)
HELP_FLAGS = {"--help", "-h", "--install-completion", "--show-completion"}
ROOT_OPTIONS_WITH_VALUES = {"--account", "-a", "--confirm"}
ACCOUNT_OPTIONS = {"--account", "-a"}
ROOT_OPTIONS_NO_VALUES = {"--yes", "--no-wait", "--unsafe"}


def rewrite_account_alias_args(argv: list[str], config: Config | None = None) -> list[str]:
    if not argv:
        return argv
    prefix: list[str] = []
    index = 0
    while index < len(argv) and argv[index].startswith("-"):
        option = argv[index]
        prefix.append(option)
        index += 1
        if option in ROOT_OPTIONS_WITH_VALUES and index < len(argv):
            prefix.append(argv[index])
            index += 1
            continue
        if option in HELP_FLAGS or option in ROOT_OPTIONS_NO_VALUES:
            continue
    if any(option in ACCOUNT_OPTIONS for option in prefix):
        return argv
    if index >= len(argv):
        return argv
    first = argv[index]
    if first in ROOT_COMMANDS or first in HELP_FLAGS:
        return argv
    cfg = config or Config()
    if first not in cfg.list_known_accounts():
        return argv
    return [*prefix, "--account", first, *argv[index + 1 :]]


def run() -> None:
    args = rewrite_account_alias_args(sys.argv[1:])
    app(args=args)


@app.callback()
def main(
    ctx: typer.Context,
    account: str | None = typer.Option(
        None,
        "--account",
        "-a",
        help="Default account alias for this command invocation",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Skip standard write confirmation prompts",
    ),
    confirm: str | None = typer.Option(
        None,
        "--confirm",
        help="Typed confirmation token for high-risk writes (<scope>:<account>)",
    ),
    no_wait: bool = typer.Option(
        False,
        "--no-wait",
        help="Fail fast instead of waiting for pacing/rate-limit permits",
    ),
    unsafe: bool = typer.Option(
        False,
        "--unsafe",
        help="Bypass safety executor for API calls in this invocation",
    ),
) -> None:
    """Root command group."""
    set_runtime_options(
        ctx,
        RuntimeOptions(account=account, yes=yes, confirm=confirm, no_wait=no_wait, unsafe=unsafe),
    )


if __name__ == "__main__":
    run()
