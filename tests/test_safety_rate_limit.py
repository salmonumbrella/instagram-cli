import pytest

from conftest import Clock

from ig_cli.safety.errors import RateLimitExceededError
from ig_cli.safety.policy import BucketPolicy, RateLimitPolicy
from ig_cli.safety.rate_limit import RateLimiter
from ig_cli.safety.state import SafetyStateStore


def test_token_bucket_refill_math(tmp_path):
    clock = Clock()
    store = SafetyStateStore(tmp_path / "state.sqlite3")
    policy = RateLimitPolicy(
        read=BucketPolicy(capacity=2, refill_per_second=1.0),
        write=BucketPolicy(capacity=1, refill_per_second=0.5),
        auth=BucketPolicy(capacity=1, refill_per_second=0.1),
    )
    limiter = RateLimiter(store, policy, time_fn=clock)

    limiter.acquire("testacct", "read", no_wait=True)
    limiter.acquire("testacct", "read", no_wait=True)
    with pytest.raises(RateLimitExceededError):
        limiter.acquire("testacct", "read", no_wait=True)

    clock.advance(1.0)
    limiter.acquire("testacct", "read", no_wait=True)


def test_per_account_buckets_are_isolated(tmp_path):
    clock = Clock()
    store = SafetyStateStore(tmp_path / "state.sqlite3")
    policy = RateLimitPolicy(
        read=BucketPolicy(capacity=1, refill_per_second=0.0),
        write=BucketPolicy(capacity=1, refill_per_second=0.0),
        auth=BucketPolicy(capacity=1, refill_per_second=0.0),
    )
    limiter = RateLimiter(store, policy, time_fn=clock)

    limiter.acquire("testacct", "read", no_wait=True)
    with pytest.raises(RateLimitExceededError):
        limiter.acquire("testacct", "read", no_wait=True)

    limiter.acquire("personal", "read", no_wait=True)
