import pytest

from ig_cli.safety.errors import CircuitOpenError
from ig_cli.safety.executor import OperationMeta, SafetyExecutor
from ig_cli.safety.policy import (
    BucketPolicy,
    CircuitBreakerPolicy,
    PacingPolicy,
    RateLimitPolicy,
    RetryPolicy,
    SafetyPolicy,
)
from ig_cli.safety.state import SafetyStateStore


def test_executor_opens_breaker_after_failure(tmp_path):
    store = SafetyStateStore(tmp_path / "state.sqlite3")
    policy = SafetyPolicy(
        circuit_breaker=CircuitBreakerPolicy(open_after_consecutive_failures=1, open_seconds=60),
        rate_limit=RateLimitPolicy(
            read=BucketPolicy(capacity=10, refill_per_second=10.0),
            write=BucketPolicy(capacity=10, refill_per_second=10.0),
            auth=BucketPolicy(capacity=10, refill_per_second=10.0),
        ),
        pacing=PacingPolicy(base_delay_seconds=0.0, jitter_seconds=0.0, max_sleep_seconds=0.0),
        retry=RetryPolicy(max_attempts_read=1, max_attempts_write=1, max_attempts_auth=1),
    )
    executor = SafetyExecutor(policy=policy, store=store)
    meta = OperationMeta(account="testacct", scope="media.info", kind="read")

    with pytest.raises(TimeoutError):
        executor.execute(meta, lambda: (_ for _ in ()).throw(TimeoutError("network")))

    with pytest.raises(CircuitOpenError):
        executor.execute(meta, lambda: {"ok": True})
