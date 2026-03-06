import datetime as dt
import random
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from time import sleep
from typing import Any, Callable

from ig_cli.safety.errors import RetryBudgetExhaustedError
from ig_cli.safety.policy import RetryPolicy


@dataclass
class RetryDecision:
    retryable: bool
    retry_after_seconds: float | None = None
    hard_open: bool = False


class RetryBudget:
    def __init__(self, remaining: int) -> None:
        self.remaining = remaining
        self.consumed = 0

    def consume(self) -> None:
        if self.remaining <= 0:
            raise RetryBudgetExhaustedError(self.consumed)
        self.remaining -= 1
        self.consumed += 1


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        now = dt.datetime.now(dt.timezone.utc)
        return max(0.0, (parsed - now).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


def classify_exception(exc: Exception) -> RetryDecision:
    status_code = getattr(exc, "status_code", None)
    retry_after = getattr(exc, "retry_after", None)
    response = getattr(exc, "response", None)
    headers: dict[str, Any] = {}
    if response is not None:
        status_code = status_code or getattr(response, "status_code", None)
        headers = getattr(response, "headers", {}) or {}
        if retry_after is None:
            retry_after = headers.get("Retry-After")

    message = str(exc).lower()
    abuse_markers = (
        "too many requests",
        "rate limit",
        "feedback_required",
        "challenge_required",
        "please wait",
        "throttl",
    )
    abuse_signal = any(marker in message for marker in abuse_markers) or status_code == 429
    retry_after_seconds = _parse_retry_after(str(retry_after) if retry_after is not None else None)

    if status_code == 429:
        return RetryDecision(
            retryable=True, retry_after_seconds=retry_after_seconds, hard_open=True
        )
    if isinstance(status_code, int) and status_code >= 500:
        return RetryDecision(
            retryable=True, retry_after_seconds=retry_after_seconds, hard_open=abuse_signal
        )
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return RetryDecision(
            retryable=True, retry_after_seconds=retry_after_seconds, hard_open=abuse_signal
        )
    if abuse_signal:
        return RetryDecision(
            retryable=True, retry_after_seconds=retry_after_seconds, hard_open=True
        )
    return RetryDecision(retryable=False, retry_after_seconds=retry_after_seconds, hard_open=False)


class RetryRunner:
    def __init__(
        self,
        policy: RetryPolicy,
        random_fn: Callable[[float, float], float] | None = None,
        sleep_fn: Callable[[float], None] = sleep,
    ) -> None:
        self.policy = policy
        self.random_fn = random_fn or random.uniform
        self.sleep_fn = sleep_fn

    def run(self, kind: str, attempt_fn: Callable[[], Any], budget: RetryBudget) -> Any:
        max_attempts = self.policy.attempts_for_kind(kind)
        attempt = 1
        while True:
            try:
                return attempt_fn()
            except Exception as exc:
                decision = classify_exception(exc)
                if not decision.retryable or attempt >= max_attempts:
                    raise
                budget.consume()
                backoff = min(
                    self.policy.max_backoff_seconds,
                    self.policy.base_backoff_seconds
                    * (self.policy.backoff_multiplier ** (attempt - 1)),
                )
                jitter = self.random_fn(0.0, self.policy.jitter_seconds)
                sleep_seconds = backoff + jitter
                if decision.retry_after_seconds is not None:
                    sleep_seconds = max(sleep_seconds, decision.retry_after_seconds)
                self.sleep_fn(sleep_seconds)
                attempt += 1
