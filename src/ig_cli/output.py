import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import typer


class _Encoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()  # pragma: no cover - optional support
        if obj.__class__.__module__.startswith("pydantic") and obj.__class__.__name__.endswith(
            "Url"
        ):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Path):
            return str(obj)
        if hasattr(obj, "__dict__"):
            return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
        return super().default(obj)


def to_json(data: Any) -> str:
    return json.dumps(data, cls=_Encoder, indent=2)


def print_json(data: Any) -> None:
    print(to_json(data))


def print_error(message: str, exit_code: int = 1) -> None:
    sys.stderr.write(json.dumps({"error": message}) + "\n")
    raise typer.Exit(code=exit_code)
