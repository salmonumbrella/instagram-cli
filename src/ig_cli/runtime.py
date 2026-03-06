from dataclasses import dataclass

import typer


@dataclass
class RuntimeOptions:
    account: str | None = None
    yes: bool = False
    confirm: str | None = None
    no_wait: bool = False
    unsafe: bool = False


def set_runtime_options(ctx: typer.Context, options: RuntimeOptions) -> None:
    ctx.obj = options


def get_runtime_options(ctx: typer.Context | None) -> RuntimeOptions:
    if ctx is not None and isinstance(ctx.obj, RuntimeOptions):
        return ctx.obj
    return RuntimeOptions()
