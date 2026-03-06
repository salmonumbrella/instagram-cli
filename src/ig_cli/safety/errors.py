class SafetyError(Exception):
    """Base safety exception."""


class CircuitOpenError(SafetyError):
    def __init__(self, account: str, scope_group: str, retry_after_seconds: float) -> None:
        super().__init__(
            f"Circuit breaker is open for account='{account}' scope='{scope_group}'. "
            f"Retry in {retry_after_seconds:.1f}s."
        )
        self.account = account
        self.scope_group = scope_group
        self.retry_after_seconds = retry_after_seconds


class RateLimitExceededError(SafetyError):
    def __init__(self, account: str, bucket: str, retry_after_seconds: float) -> None:
        super().__init__(
            f"Rate limit bucket '{bucket}' exhausted for account='{account}'. "
            f"Retry in {retry_after_seconds:.1f}s."
        )
        self.account = account
        self.bucket = bucket
        self.retry_after_seconds = retry_after_seconds


class RetryBudgetExhaustedError(SafetyError):
    def __init__(self, attempts: int) -> None:
        super().__init__(f"Retry budget exhausted after {attempts} retries.")
        self.attempts = attempts


class WriteGuardError(SafetyError):
    """Raised when write safety checks fail."""
