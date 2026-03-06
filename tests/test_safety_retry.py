import pytest

from ig_cli.safety.errors import RetryBudgetExhaustedError
from ig_cli.safety.policy import RetryPolicy
from ig_cli.safety.retry import RetryBudget, RetryRunner


def test_retry_stops_on_non_retryable_error():
    runner = RetryRunner(RetryPolicy())
    budget = RetryBudget(remaining=8)
    attempts = {"count": 0}

    def fn():
        attempts["count"] += 1
        raise ValueError("validation failed")

    with pytest.raises(ValueError):
        runner.run("read", fn, budget)
    assert attempts["count"] == 1


def test_retry_respects_command_budget():
    policy = RetryPolicy(max_attempts_read=4, jitter_seconds=0.0)
    runner = RetryRunner(policy, random_fn=lambda _a, _b: 0.0, sleep_fn=lambda _s: None)
    budget = RetryBudget(remaining=1)
    attempts = {"count": 0}

    def fn():
        attempts["count"] += 1
        raise TimeoutError("transient")

    with pytest.raises(RetryBudgetExhaustedError):
        runner.run("read", fn, budget)
    assert attempts["count"] == 2


def test_retry_uses_exponential_backoff():
    sleeps: list[float] = []
    policy = RetryPolicy(
        max_attempts_read=4,
        base_backoff_seconds=1.0,
        backoff_multiplier=2.0,
        max_backoff_seconds=60.0,
        jitter_seconds=0.0,
    )
    runner = RetryRunner(
        policy,
        random_fn=lambda _a, _b: 0.0,
        sleep_fn=lambda s: sleeps.append(s),
    )
    budget = RetryBudget(remaining=8)
    attempts = {"count": 0}

    def fn():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise TimeoutError("transient")
        return {"ok": True}

    result = runner.run("read", fn, budget)
    assert result["ok"] is True
    assert sleeps == [1.0, 2.0]
