from time import sleep
from typing import Callable

from ig_cli.safety.errors import RateLimitExceededError
from ig_cli.safety.policy import BucketPolicy, RateLimitPolicy
from ig_cli.safety.state import SafetyStateStore


class RateLimiter:
    def __init__(
        self,
        store: SafetyStateStore,
        policy: RateLimitPolicy,
        time_fn: Callable[[], float],
    ) -> None:
        self.store = store
        self.policy = policy
        self.time_fn = time_fn

    def _bucket(self, kind: str) -> tuple[str, BucketPolicy]:
        if kind == "write":
            return "write", self.policy.write
        if kind == "auth":
            return "auth", self.policy.auth
        return "read", self.policy.read

    def acquire(
        self,
        account: str,
        kind: str,
        no_wait: bool = False,
        sleep_fn: Callable[[float], None] = sleep,
    ) -> dict[str, float | str]:
        bucket_name, bucket_policy = self._bucket(kind)
        now = self.time_fn()
        record = self.store.get_bucket(account, bucket_name, bucket_policy.capacity, now)
        elapsed = max(0.0, now - float(record["last_refill_at"]))
        tokens = min(
            bucket_policy.capacity,
            float(record["tokens"]) + elapsed * bucket_policy.refill_per_second,
        )

        if tokens < 1.0:
            if bucket_policy.refill_per_second <= 0:
                wait_seconds = float("inf")
            else:
                wait_seconds = (1.0 - tokens) / bucket_policy.refill_per_second
            if no_wait:
                raise RateLimitExceededError(account, bucket_name, wait_seconds)
            if wait_seconds == float("inf"):
                raise RateLimitExceededError(account, bucket_name, wait_seconds)
            sleep_fn(wait_seconds)
            now = self.time_fn()
            elapsed = max(0.0, now - float(record["last_refill_at"]))
            tokens = min(
                bucket_policy.capacity,
                float(record["tokens"]) + elapsed * bucket_policy.refill_per_second,
            )

        tokens = max(0.0, tokens - 1.0)
        self.store.upsert_bucket(account, bucket_name, tokens=tokens, last_refill_at=now)
        return {
            "bucket": bucket_name,
            "tokens": tokens,
            "capacity": bucket_policy.capacity,
            "refill_per_second": bucket_policy.refill_per_second,
        }

    def snapshot(self, account: str) -> list[dict[str, float | str]]:
        return self.store.list_buckets(account)
