import inspect
from typing import Any

from instagrapi import Client

EMPTY = inspect.Signature.empty


def list_client_methods() -> list[str]:
    return sorted(
        name for name in dir(Client) if not name.startswith("_") and callable(getattr(Client, name))
    )


def get_method_signature(method_name: str) -> dict[str, Any]:
    attr = getattr(Client, method_name, None)
    if attr is None or not callable(attr):
        raise ValueError(f"Unknown client method: {method_name}")
    signature = inspect.signature(attr)
    parameters: list[dict[str, Any]] = []
    for param in signature.parameters.values():
        if param.name == "self":
            continue
        parameters.append(
            {
                "name": param.name,
                "kind": str(param.kind),
                "required": param.default is EMPTY,
                "default": None if param.default is EMPTY else param.default,
            }
        )
    return {"name": method_name, "parameters": parameters}


def summarize_cli_coverage(curated_methods: set[str]) -> dict[str, Any]:
    upstream_methods = set(list_client_methods())
    covered = sorted(curated_methods & upstream_methods)
    missing = sorted(upstream_methods - curated_methods)
    total_upstream = len(upstream_methods)
    covered_count = len(covered)
    return {
        "total_upstream": total_upstream,
        "covered_count": covered_count,
        "missing_count": len(missing),
        "coverage_percent": round((covered_count / total_upstream) * 100, 2)
        if total_upstream
        else 0.0,
        "covered": covered,
        "missing": missing,
    }
