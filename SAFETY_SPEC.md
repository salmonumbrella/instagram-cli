# Instagram CLI Safety Spec (Typer-Compatible, v1)

## Scope
This spec defines a safety layer for all Instagram API calls in `ig` with concrete defaults for:
- Persistent circuit breaker
- Per-account rate limiting
- Global request pacing with jitter
- Retry budget and backoff
- Write-action confirmation guard
- Observability via `ig safety status`

The design is implementable with the current scaffold (`src/ig_cli/main.py`) and Python stdlib + existing dependencies.

## Default Policy
Use these defaults unless overridden in config.

```toml
[safety]
enabled = true

[safety.circuit_breaker]
window_seconds = 120
open_after_consecutive_failures = 4
open_after_failures_in_window = 8
open_seconds = 600
hard_open_seconds = 1800
half_open_max_probes = 2
close_after_consecutive_successes = 2

[safety.rate_limit.read]
capacity = 20
refill_per_second = 0.3333

[safety.rate_limit.write]
capacity = 4
refill_per_second = 0.0667

[safety.rate_limit.auth]
capacity = 2
refill_per_second = 0.0067

[safety.pacing]
base_delay_seconds = 1.2
jitter_seconds = 0.4
max_sleep_seconds = 5.0

[safety.retry]
max_attempts_read = 4
max_attempts_write = 2
max_attempts_auth = 2
command_retry_budget = 8
base_backoff_seconds = 1.0
max_backoff_seconds = 60.0
backoff_multiplier = 2.0
jitter_seconds = 0.25

[safety.write_guard]
require_confirmation_for_write = true
require_typed_confirm_for_high_risk = true
allow_yes_flag = true
fail_if_non_tty_without_yes = true
```

## Operation Model
Each API call must include metadata:

```python
OperationMeta(
    account: str,
    scope: str,  # e.g. "media.upload", "dm.send", "user.info"
    kind: Literal["read", "write", "auth"],
    high_risk: bool = False,
)
```

`kind` controls limiter bucket and retry ceiling.

## Execution Order
For every API call, run safety controls in this order:
1. Write guard check (only for `kind="write"`)
2. Circuit breaker gate
3. Per-account rate limiter acquire
4. Global pacing sleep
5. Retry wrapper around the API call
6. Record success/failure back into breaker and status state

This order avoids hammering endpoints when already unhealthy and ensures pacing/rate limits apply to retries too.

## Persistent Circuit Breaker
State is persisted across process runs.

### States
- `closed`: normal traffic
- `open`: all requests blocked until `opened_until`
- `half_open`: allow up to `half_open_max_probes` probe attempts

### Open rules
Open breaker when either condition is met:
- `consecutive_failures >= 4`
- `failures_in_last_120s >= 8`

Immediate hard-open (`hard_open_seconds = 1800`) for anti-abuse signals:
- HTTP 429
- Challenge/feedback-required style exceptions from `instagrapi`

Normal open duration: 600s.

### Recovery rules
- On timeout expiry, move `open -> half_open`
- In half-open, close after `2` consecutive successes
- Any failure in half-open returns to `open`

### Persistence keying
Persist by `(account, scope_group)` where `scope_group` is command family (e.g. `media`, `dm`, `live`, `global`).

## Per-Account Rate Limiting
Use token buckets per account and operation kind:
- `read`: burst 20, refill ~20/min
- `write`: burst 4, refill ~4/min
- `auth`: burst 2, refill ~2/5min

Behavior:
- If token available: consume and continue
- If empty: compute wait time and sleep (up to pacing max) or fail fast if `--no-wait` is used later

State is persistent so separate CLI invocations share limits.

## Global Request Pacing + Jitter
Before every attempt (including retries):
- Compute `target = last_request_at + base_delay + uniform(-jitter, +jitter)`
- Sleep `max(0, target - now)`, capped at `max_sleep_seconds`
- Update `last_request_at` after sleep

Defaults yield about one request every 0.8-1.6s globally.

## Retry Budget + Backoff
Retries are allowed only for transient failures.

### Retryable failures
- Network/connect timeout
- HTTP 5xx
- HTTP 429

### Non-retryable failures
- HTTP 4xx (except 429)
- Validation/auth errors that require user action

### Limits
- Read: max 4 attempts
- Write: max 2 attempts
- Auth: max 2 attempts
- Additional global budget per top-level command: 8 retries total

### Backoff
Attempt `n` (first retry is `n=1`):
- `sleep = min(max_backoff, base_backoff * multiplier^(n-1)) + uniform(0, jitter)`
- Defaults: `1s, 2s, 4s, ...` up to `60s`
- If response has `Retry-After`, use `max(retry_after, computed_sleep)`

Budget exhaustion produces a deterministic error (`retry_budget_exhausted`) and counts as a breaker failure.

## Write-Action Confirmation Guard
Applies to all `kind="write"` operations.

### Default behavior
- Interactive TTY: prompt `Proceed with write action <scope> for <account>? [y/N]`
- Non-interactive: fail unless `--yes`

### High-risk writes
For destructive actions (delete media/comment, account mutation, ending live, etc.):
- Require typed confirmation token: `--confirm "<scope>:<account>"`
- `--yes` alone is insufficient when `high_risk=True`

Failures return exit code `2` with JSON error payload.

## Observability: `ig safety status`
Add a new command:

```bash
ig safety status --account <alias>
```

JSON output fields:
- `timestamp`
- `account`
- `policy` (effective defaults + overrides)
- `circuit_breaker` (state, opened_until, counters)
- `rate_limit` (tokens/capacity/refill for read/write/auth)
- `pacing` (last_request_at, next_earliest_request_at)
- `retry` (attempt ceilings, remaining command budget)
- `write_guard` (modes and required flags)

If no account is passed, use default account from config; otherwise return a clear error.

## File Layout Proposal

```text
src/ig_cli/
  main.py
  config.py
  safety/
    __init__.py
    policy.py        # dataclasses + TOML parsing + defaults
    state.py         # sqlite persistence for breaker/limiter/pacing snapshot
    breaker.py       # circuit breaker state machine
    rate_limit.py    # token bucket logic
    pacing.py        # global pacing + jitter
    retry.py         # retry budget + backoff policy
    guard.py         # write confirmation logic
    executor.py      # execute_with_safety(meta, fn)
    commands.py      # Typer sub-app: `ig safety status`
```

Integration points:
- `main.py`: register `safety.commands.app` as `ig safety`
- Future command modules: wrap all `instagrapi` calls via `execute_with_safety(...)`

## Persistent State Layout (sqlite)
Use `~/.config/ig-cli/safety_state.sqlite3`.

Tables:
- `breaker_state(account TEXT, scope_group TEXT, state TEXT, consecutive_failures INT, failures_window INT, window_started_at REAL, opened_until REAL, half_open_probes INT, consecutive_successes INT, updated_at REAL, PRIMARY KEY(account, scope_group))`
- `rate_bucket(account TEXT, bucket TEXT, tokens REAL, last_refill_at REAL, updated_at REAL, PRIMARY KEY(account, bucket))`
- `global_state(key TEXT PRIMARY KEY, value TEXT, updated_at REAL)`

`global_state` key used initially: `last_request_at`.

## Minimal Tests
Add these tests first:

1. `tests/test_safety_breaker.py`
- `test_breaker_opens_after_consecutive_failures`
- `test_breaker_persists_open_state_across_instances`
- `test_breaker_half_open_closes_after_successes`

2. `tests/test_safety_rate_limit.py`
- `test_token_bucket_refill_math`
- `test_per_account_buckets_are_isolated`

3. `tests/test_safety_pacing.py`
- `test_pacing_applies_global_delay_with_jitter_bounds`

4. `tests/test_safety_retry.py`
- `test_retry_stops_on_non_retryable_error`
- `test_retry_respects_command_budget`
- `test_retry_uses_exponential_backoff`

5. `tests/test_safety_guard.py`
- `test_write_guard_requires_yes_in_non_tty`
- `test_high_risk_requires_typed_confirm`

6. `tests/test_safety_status_command.py`
- `test_safety_status_returns_required_json_fields`

All tests can use `tmp_path` + `monkeypatch` for config/state location and time/random control.

## Rollout Sequence
1. Implement `policy.py` and `state.py`
2. Implement breaker + rate limiter + pacing
3. Implement retry and guard
4. Add `execute_with_safety`
5. Add `ig safety status`
6. Add tests above and make them pass
