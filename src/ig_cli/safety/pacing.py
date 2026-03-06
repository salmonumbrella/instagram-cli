import random
from time import sleep
from typing import Callable

from ig_cli.safety.errors import RateLimitExceededError
from ig_cli.safety.policy import PacingPolicy
from ig_cli.safety.state import SafetyStateStore


class GlobalPacer:
    def __init__(
        self,
        store: SafetyStateStore,
        policy: PacingPolicy,
        time_fn: Callable[[], float],
        random_fn: Callable[[float, float], float] | None = None,
    ) -> None:
        self.store = store
        self.policy = policy
        self.time_fn = time_fn
        self.random_fn = random_fn or random.uniform

    def acquire(
        self, no_wait: bool = False, sleep_fn: Callable[[float], None] = sleep
    ) -> dict[str, float]:
        now = self.time_fn()
        last_request_at = self.store.get_global_float("last_request_at", default=0.0)
        jitter = self.random_fn(-self.policy.jitter_seconds, self.policy.jitter_seconds)
        target = last_request_at + self.policy.base_delay_seconds + jitter
        delay = max(0.0, target - now)
        delay = min(delay, self.policy.max_sleep_seconds)
        if no_wait and delay > 0:
            raise RateLimitExceededError(
                account="global", bucket="pacing", retry_after_seconds=delay
            )
        if delay > 0:
            sleep_fn(delay)
        now = self.time_fn()
        self.store.set_global_float("last_request_at", now)
        return {
            "last_request_at": now,
            "next_earliest_request_at": now + self.policy.base_delay_seconds,
            "slept_seconds": delay,
        }

    def snapshot(self) -> dict[str, float]:
        last_request_at = self.store.get_global_float("last_request_at", default=0.0)
        return {
            "last_request_at": last_request_at,
            "next_earliest_request_at": last_request_at + self.policy.base_delay_seconds,
        }
