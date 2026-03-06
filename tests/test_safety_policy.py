import pytest

from ig_cli.config import Config
from ig_cli.safety.policy import load_policy


def test_load_policy_rejects_impossible_half_open_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("IG_CLI_CONFIG_DIR", str(tmp_path))
    cfg = Config()
    cfg.safety_policy_file.write_text(
        """
[safety.circuit_breaker]
half_open_max_probes = 1
close_after_consecutive_successes = 2
""".strip()
    )

    with pytest.raises(ValueError, match="close_after_consecutive_successes"):
        load_policy(cfg)
