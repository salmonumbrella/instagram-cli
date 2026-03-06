import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any


DIR_MODE = 0o700
FILE_MODE = 0o600


def _ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(DIR_MODE)


def _atomic_write_text(path: Path, content: str) -> None:
    _ensure_private_dir(path.parent)
    fd, tmp_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        os.chmod(tmp_path, FILE_MODE)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        path.chmod(FILE_MODE)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


def _enforce_private_file(path: Path, kind: str) -> None:
    if os.name != "posix":
        return
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise PermissionError(f"{kind} file {path} must not be accessible by group or others.")


class Config:
    def __init__(self) -> None:
        config_dir = os.environ.get("IG_CLI_CONFIG_DIR")
        self.config_dir = Path(config_dir) if config_dir else Path.home() / ".config" / "ig-cli"
        self.sessions_dir = self.config_dir / "sessions"
        self.credentials_dir = self.config_dir / "credentials"
        self.config_file = self.config_dir / "config.json"
        self.safety_policy_file = self.config_dir / "safety.toml"
        self.safety_state_file = self.config_dir / "safety_state.sqlite3"
        _ensure_private_dir(self.config_dir)
        _ensure_private_dir(self.sessions_dir)
        _ensure_private_dir(self.credentials_dir)

    def _load_config(self) -> dict[str, Any]:
        if self.config_file.exists():
            return json.loads(self.config_file.read_text())
        return {}

    def _save_config(self, data: dict[str, Any]) -> None:
        _atomic_write_text(self.config_file, json.dumps(data, indent=2))

    def get_default_account(self) -> str | None:
        return self._load_config().get("default_account")

    def set_default_account(self, alias: str) -> None:
        cfg = self._load_config()
        cfg["default_account"] = alias
        self._save_config(cfg)

    def account_settings(self, alias: str) -> dict[str, Any]:
        cfg = self._load_config()
        accounts = cfg.get("accounts", {})
        account_settings = accounts.get(alias, {})
        if isinstance(account_settings, dict):
            return account_settings
        raise ValueError(f"Account settings for '{alias}' in {self.config_file} must be an object.")

    def global_runtime_settings(self) -> dict[str, Any]:
        cfg = self._load_config()
        runtime = cfg.get("runtime", {})
        if isinstance(runtime, dict):
            return runtime
        raise ValueError(f"Runtime settings in {self.config_file} must be an object.")

    def session_path(self, alias: str) -> Path:
        return self.sessions_dir / f"{alias}.json"

    def credential_paths(self, alias: str) -> list[Path]:
        return [
            self.credentials_dir / f"{alias}.toml",
            self.credentials_dir / f"{alias}.json",
        ]

    def default_account_hint(self) -> str:
        return f"Pass --account <alias> or set default_account in {self.config_file}."

    def account_material_hint(self, alias: str) -> str:
        credentials = " or ".join(str(path) for path in self.credential_paths(alias))
        return f"Create a session at {self.session_path(alias)} or credentials at {credentials}."

    def save_session(self, alias: str, data: dict[str, Any]) -> None:
        _atomic_write_text(self.session_path(alias), json.dumps(data, indent=2))

    def load_session(self, alias: str) -> dict[str, Any] | None:
        path = self.session_path(alias)
        if path.exists():
            _enforce_private_file(path, "Session")
            return json.loads(path.read_text())
        return None

    def list_accounts(self) -> list[str]:
        return sorted([p.stem for p in self.sessions_dir.glob("*.json")])

    def list_known_accounts(self) -> list[str]:
        accounts = set(self.list_accounts())
        for path in self.credentials_dir.glob("*.toml"):
            accounts.add(path.stem)
        for path in self.credentials_dir.glob("*.json"):
            accounts.add(path.stem)
        default_account = self.get_default_account()
        if default_account:
            accounts.add(default_account)
        return sorted(accounts)

    def load_credentials(self, alias: str) -> dict[str, str] | None:
        for path in self.credential_paths(alias):
            if path.exists():
                _enforce_private_file(path, "Credential")
                if path.suffix == ".toml":
                    import tomllib

                    return tomllib.loads(path.read_text())
                return json.loads(path.read_text())
        return None
