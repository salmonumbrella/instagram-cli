from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ig_cli.config import Config


@dataclass
class CircuitBreakerPolicy:
    window_seconds: int = 120
    open_after_consecutive_failures: int = 4
    open_after_failures_in_window: int = 8
    open_seconds: int = 600
    hard_open_seconds: int = 1800
    half_open_max_probes: int = 2
    close_after_consecutive_successes: int = 2

    def validate(self) -> None:
        if self.open_after_consecutive_failures < 1:
            raise ValueError("circuit_breaker.open_after_consecutive_failures must be at least 1")
        if self.open_after_failures_in_window < 1:
            raise ValueError("circuit_breaker.open_after_failures_in_window must be at least 1")
        if self.open_seconds <= 0:
            raise ValueError("circuit_breaker.open_seconds must be greater than 0")
        if self.hard_open_seconds <= 0:
            raise ValueError("circuit_breaker.hard_open_seconds must be greater than 0")
        if self.half_open_max_probes < 1:
            raise ValueError("circuit_breaker.half_open_max_probes must be at least 1")
        if self.close_after_consecutive_successes < 1:
            raise ValueError("circuit_breaker.close_after_consecutive_successes must be at least 1")
        if self.close_after_consecutive_successes > self.half_open_max_probes:
            raise ValueError(
                "circuit_breaker.close_after_consecutive_successes cannot exceed "
                "circuit_breaker.half_open_max_probes"
            )


@dataclass
class BucketPolicy:
    capacity: float
    refill_per_second: float


@dataclass
class RateLimitPolicy:
    read: BucketPolicy = field(
        default_factory=lambda: BucketPolicy(capacity=20, refill_per_second=0.3333)
    )
    write: BucketPolicy = field(
        default_factory=lambda: BucketPolicy(capacity=4, refill_per_second=0.0667)
    )
    auth: BucketPolicy = field(
        default_factory=lambda: BucketPolicy(capacity=2, refill_per_second=0.0067)
    )


@dataclass
class PacingPolicy:
    base_delay_seconds: float = 1.2
    jitter_seconds: float = 0.4
    max_sleep_seconds: float = 5.0


@dataclass
class RetryPolicy:
    max_attempts_read: int = 4
    max_attempts_write: int = 2
    max_attempts_auth: int = 2
    command_retry_budget: int = 8
    base_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 60.0
    backoff_multiplier: float = 2.0
    jitter_seconds: float = 0.25

    def attempts_for_kind(self, kind: str) -> int:
        if kind == "read":
            return self.max_attempts_read
        if kind == "write":
            return self.max_attempts_write
        if kind == "auth":
            return self.max_attempts_auth
        return self.max_attempts_read


@dataclass
class WriteGuardPolicy:
    require_confirmation_for_write: bool = True
    require_typed_confirm_for_high_risk: bool = True
    allow_yes_flag: bool = True
    fail_if_non_tty_without_yes: bool = True


@dataclass
class SafetyPolicy:
    enabled: bool = True
    circuit_breaker: CircuitBreakerPolicy = field(default_factory=CircuitBreakerPolicy)
    rate_limit: RateLimitPolicy = field(default_factory=RateLimitPolicy)
    pacing: PacingPolicy = field(default_factory=PacingPolicy)
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    write_guard: WriteGuardPolicy = field(default_factory=WriteGuardPolicy)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        self.circuit_breaker.validate()


def _update_dataclass(target: Any, updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        if not hasattr(target, key):
            continue
        current = getattr(target, key)
        if hasattr(current, "__dataclass_fields__") and isinstance(value, dict):
            _update_dataclass(current, value)
        else:
            setattr(target, key, value)


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    import tomllib

    return tomllib.loads(path.read_text())


def load_policy(config: Config | None = None) -> SafetyPolicy:
    cfg = config or Config()
    policy = SafetyPolicy()
    data = _load_toml(cfg.safety_policy_file)
    safety_data = data.get("safety", {})
    if isinstance(safety_data, dict):
        _update_dataclass(policy, safety_data)
    try:
        policy.validate()
    except ValueError as exc:
        raise ValueError(f"Invalid safety policy in {cfg.safety_policy_file}: {exc}") from exc
    return policy
