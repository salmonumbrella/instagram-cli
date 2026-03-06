import pytest

from conftest import Clock

from ig_cli.safety.breaker import CircuitBreaker
from ig_cli.safety.errors import CircuitOpenError
from ig_cli.safety.policy import CircuitBreakerPolicy
from ig_cli.safety.state import SafetyStateStore


def test_breaker_opens_after_consecutive_failures(tmp_path):
    clock = Clock()
    store = SafetyStateStore(tmp_path / "state.sqlite3")
    policy = CircuitBreakerPolicy(open_after_consecutive_failures=2, open_seconds=30)
    breaker = CircuitBreaker(store, policy, time_fn=clock)

    breaker.record_failure("testacct", "media")
    breaker.record_failure("testacct", "media")

    with pytest.raises(CircuitOpenError):
        breaker.allow("testacct", "media")


def test_breaker_persists_open_state_across_instances(tmp_path):
    clock = Clock()
    store = SafetyStateStore(tmp_path / "state.sqlite3")
    policy = CircuitBreakerPolicy(open_after_consecutive_failures=1, open_seconds=60)
    breaker = CircuitBreaker(store, policy, time_fn=clock)
    breaker.record_failure("testacct", "dm")

    second_instance = CircuitBreaker(store, policy, time_fn=clock)
    with pytest.raises(CircuitOpenError):
        second_instance.allow("testacct", "dm")


def test_breaker_half_open_closes_after_successes(tmp_path):
    clock = Clock()
    store = SafetyStateStore(tmp_path / "state.sqlite3")
    policy = CircuitBreakerPolicy(
        open_after_consecutive_failures=1,
        open_seconds=10,
        half_open_max_probes=3,
        close_after_consecutive_successes=2,
    )
    breaker = CircuitBreaker(store, policy, time_fn=clock)
    breaker.record_failure("testacct", "auth")

    clock.advance(11)
    breaker.allow("testacct", "auth")
    breaker.record_success("testacct", "auth")
    breaker.allow("testacct", "auth")
    breaker.record_success("testacct", "auth")
    breaker.allow("testacct", "auth")


def test_breaker_reopens_when_half_open_probe_budget_is_exhausted(tmp_path):
    clock = Clock()
    store = SafetyStateStore(tmp_path / "state.sqlite3")
    policy = CircuitBreakerPolicy(
        open_after_consecutive_failures=1,
        open_seconds=10,
        half_open_max_probes=1,
        close_after_consecutive_successes=2,
    )
    breaker = CircuitBreaker(store, policy, time_fn=clock)
    breaker.record_failure("testacct", "auth")

    clock.advance(11)
    breaker.allow("testacct", "auth")
    breaker.record_success("testacct", "auth")

    with pytest.raises(CircuitOpenError) as exc_info:
        breaker.allow("testacct", "auth")

    record = store.get_breaker("testacct", "auth")
    assert exc_info.value.retry_after_seconds == pytest.approx(10.0)
    assert record["state"] == "open"
    assert record["half_open_probes"] == 0
    assert record["consecutive_successes"] == 0
