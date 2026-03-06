from typing import Callable

from ig_cli.safety.errors import CircuitOpenError
from ig_cli.safety.policy import CircuitBreakerPolicy
from ig_cli.safety.state import SafetyStateStore


class CircuitBreaker:
    def __init__(
        self,
        store: SafetyStateStore,
        policy: CircuitBreakerPolicy,
        time_fn: Callable[[], float],
    ) -> None:
        self.store = store
        self.policy = policy
        self.time_fn = time_fn

    def allow(self, account: str, scope_group: str) -> None:
        now = self.time_fn()
        record = self.store.get_breaker(account, scope_group)
        state = record["state"]

        if state == "open":
            opened_until = float(record["opened_until"])
            if now < opened_until:
                raise CircuitOpenError(account, scope_group, opened_until - now)
            record.update(
                {
                    "state": "half_open",
                    "half_open_probes": 0,
                    "consecutive_successes": 0,
                }
            )
            self.store.upsert_breaker(account, scope_group, record)
            state = "half_open"

        if state == "half_open":
            probes = int(record["half_open_probes"])
            if probes >= self.policy.half_open_max_probes:
                opened_until = now + self.policy.open_seconds
                record.update(
                    {
                        "state": "open",
                        "opened_until": opened_until,
                        "half_open_probes": 0,
                        "consecutive_successes": 0,
                    }
                )
                self.store.upsert_breaker(account, scope_group, record)
                retry_after = max(1.0, opened_until - now)
                raise CircuitOpenError(account, scope_group, retry_after)
            record["half_open_probes"] = probes + 1
            self.store.upsert_breaker(account, scope_group, record)

    def record_success(self, account: str, scope_group: str) -> None:
        record = self.store.get_breaker(account, scope_group)
        if record["state"] == "half_open":
            successes = int(record["consecutive_successes"]) + 1
            record["consecutive_successes"] = successes
            if successes >= self.policy.close_after_consecutive_successes:
                record.update(
                    {
                        "state": "closed",
                        "consecutive_failures": 0,
                        "failures_window": 0,
                        "window_started_at": 0.0,
                        "opened_until": 0.0,
                        "half_open_probes": 0,
                        "consecutive_successes": 0,
                    }
                )
        else:
            record["consecutive_failures"] = 0
        self.store.upsert_breaker(account, scope_group, record)

    def record_failure(self, account: str, scope_group: str, is_abuse: bool = False) -> None:
        now = self.time_fn()
        record = self.store.get_breaker(account, scope_group)

        window_started_at = float(record["window_started_at"])
        if window_started_at <= 0 or (now - window_started_at) > self.policy.window_seconds:
            failures_window = 1
            window_started_at = now
        else:
            failures_window = int(record["failures_window"]) + 1

        consecutive_failures = int(record["consecutive_failures"]) + 1
        record["window_started_at"] = window_started_at
        record["failures_window"] = failures_window
        record["consecutive_failures"] = consecutive_failures

        should_open = (
            record["state"] == "half_open"
            or is_abuse
            or consecutive_failures >= self.policy.open_after_consecutive_failures
            or failures_window >= self.policy.open_after_failures_in_window
        )
        if should_open:
            open_seconds = self.policy.hard_open_seconds if is_abuse else self.policy.open_seconds
            record.update(
                {
                    "state": "open",
                    "opened_until": now + open_seconds,
                    "half_open_probes": 0,
                    "consecutive_successes": 0,
                }
            )
        self.store.upsert_breaker(account, scope_group, record)

    def snapshot(self, account: str) -> list[dict[str, float | int | str]]:
        rows = self.store.list_breakers(account)
        now = self.time_fn()
        result: list[dict[str, float | int | str]] = []
        for row in rows:
            opened_until = float(row["opened_until"])
            row["retry_after_seconds"] = (
                max(0.0, opened_until - now) if row["state"] == "open" else 0.0
            )
            result.append(row)
        return result
