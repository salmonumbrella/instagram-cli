import stat

from ig_cli.config import Config
from ig_cli.safety.state import SafetyStateStore


def test_config_uses_private_permissions(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.set_default_account("testacct")
    cfg.save_session("testacct", {"session": "secret"})

    assert stat.S_IMODE(cfg.config_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(cfg.sessions_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(cfg.credentials_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(cfg.config_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(cfg.session_path("testacct").stat().st_mode) == 0o600


def test_safety_state_db_uses_private_permissions(tmp_path):
    db_path = tmp_path / "state" / "safety_state.sqlite3"
    store = SafetyStateStore(db_path)

    # Force schema creation before checking the file mode.
    store.get_global_float("last_request_at")

    assert stat.S_IMODE(db_path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(db_path.stat().st_mode) == 0o600
