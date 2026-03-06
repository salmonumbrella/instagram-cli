from importlib.resources import files


def load_help_text(filename: str) -> str:
    return files("ig_cli").joinpath(filename).read_text(encoding="utf-8")
