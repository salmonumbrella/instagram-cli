import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Literal

from ig_cli.config import Config
from ig_cli.safety.breaker import CircuitBreaker
from ig_cli.safety.guard import WriteGuard
from ig_cli.safety.pacing import GlobalPacer
from ig_cli.safety.policy import SafetyPolicy, load_policy
from ig_cli.safety.rate_limit import RateLimiter
from ig_cli.safety.retry import RetryBudget, RetryRunner, classify_exception
from ig_cli.safety.state import SafetyStateStore


OperationKind = Literal["read", "write", "auth"]


@dataclass
class OperationMeta:
    account: str
    scope: str
    kind: OperationKind
    high_risk: bool = False

    @property
    def scope_group(self) -> str:
        if "." in self.scope:
            return self.scope.split(".", 1)[0]
        return self.scope or "global"


class SafetyExecutor:
    def __init__(
        self,
        policy: SafetyPolicy,
        store: SafetyStateStore,
        time_fn: Callable[[], float] = time.time,
    ) -> None:
        self.policy = policy
        self.store = store
        self.time_fn = time_fn
        self.breaker = CircuitBreaker(store, policy.circuit_breaker, time_fn=time_fn)
        self.rate_limiter = RateLimiter(store, policy.rate_limit, time_fn=time_fn)
        self.pacer = GlobalPacer(store, policy.pacing, time_fn=time_fn)
        self.retry = RetryRunner(policy.retry)
        self.guard = WriteGuard(policy.write_guard)

    @classmethod
    def from_config(cls, config: Config | None = None) -> "SafetyExecutor":
        cfg = config or Config()
        policy = load_policy(cfg)
        store = SafetyStateStore(cfg.safety_state_file)
        return cls(policy=policy, store=store)

    def execute(
        self,
        meta: OperationMeta,
        fn: Callable[[], Any],
        *,
        yes: bool = False,
        confirm_token: str | None = None,
        no_wait: bool = False,
        stdin_isatty: bool | None = None,
    ) -> Any:
        if not self.policy.enabled:
            return fn()

        self.guard.enforce(
            account=meta.account,
            scope=meta.scope,
            kind=meta.kind,
            high_risk=meta.high_risk,
            yes=yes,
            confirm_token=confirm_token,
            stdin_isatty=stdin_isatty,
        )

        budget = RetryBudget(self.policy.retry.command_retry_budget)

        def attempt() -> Any:
            self.breaker.allow(meta.account, meta.scope_group)
            self.rate_limiter.acquire(meta.account, meta.kind, no_wait=no_wait)
            self.pacer.acquire(no_wait=no_wait)
            try:
                result = fn()
            except Exception as exc:
                decision = classify_exception(exc)
                self.breaker.record_failure(
                    meta.account,
                    meta.scope_group,
                    is_abuse=decision.hard_open,
                )
                raise
            self.breaker.record_success(meta.account, meta.scope_group)
            return result

        return self.retry.run(meta.kind, attempt, budget)

    def snapshot(self, account: str) -> dict[str, Any]:
        return {
            "timestamp": self.time_fn(),
            "account": account,
            "policy": self.policy.to_dict(),
            "circuit_breaker": self.breaker.snapshot(account),
            "rate_limit": self.rate_limiter.snapshot(account),
            "pacing": self.pacer.snapshot(),
            "retry": asdict(self.policy.retry),
            "write_guard": asdict(self.policy.write_guard),
        }


def build_safety_executor(config: Config | None = None) -> SafetyExecutor:
    return SafetyExecutor.from_config(config=config)
