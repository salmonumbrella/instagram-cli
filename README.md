# instagram-cli

Agent-friendly CLI for Instagram built on [instagrapi](https://github.com/subzeroid/instagrapi).

Every command outputs JSON to stdout and errors to stderr. Designed for scripting, automation, and agent workflows -- not interactive browsing.

## Installation

```bash
# Recommended (isolated install, no venv needed)
uv tool install instagram-cli

# Or via pip
pip install instagram-cli
```

The binary is called `ig`.

## Quick Start

```bash
# Login and save a session
ig auth login --alias myshop

# Check who you're logged in as
ig auth whoami

# Get user info
ig user info natgeo

# List recent media for a user
ig media user natgeo

# Upload a photo
ig --yes media upload-photo ./product.jpg --caption "New arrival"
```

All output is JSON. Pipe to `jq` for field extraction:

```bash
ig user info natgeo | jq '.follower_count'
```

## Multi-Account

Manage multiple Instagram accounts from a single CLI:

```bash
# Login to different accounts
ig auth login --alias myshop
ig auth login --alias personal

# Set default account
ig auth default myshop

# Use a specific account for one command
ig --account personal user info someuser

# Shorthand: use the alias directly as a positional prefix
ig personal user info someuser

# List all saved accounts
ig auth list
```

## Command Groups

| Group | Commands | Description |
|-------|----------|-------------|
| `auth` | `login`, `logout`, `default`, `list`, `session`, `whoami`, `validate` | Account login, session management, identity |
| `user` | `info`, `followers`, `following` | User profiles and relationships |
| `media` | `info`, `user`, `upload-photo`, `delete` | Media metadata, upload, deletion |
| `story` | `list`, `viewers`, `upload-photo`, `upload-video` | Story publishing and analytics |
| `live` | `create`, `start`, `end`, `info`, `comments`, `viewers` | Live streaming lifecycle |
| `insight` | `account`, `media` | Account and media analytics |
| `raw` | `methods`, `coverage`, `schema`, `call` | Direct access to instagrapi methods |
| `safety` | `status`, `reset` | Inspect and reset safety layer state |

Run `ig <group> --help` for full usage of any group.

## Live Streaming

The `live` group manages the full broadcast lifecycle:

```bash
# Create a broadcast (returns RTMP server + stream key)
ig --yes live create --title "Going Live"
# Output: { "broadcast_id": "123", "stream_server": "rtmp://...", "stream_key": "..." }

# Point OBS or ffmpeg at the RTMP URL, then start the broadcast
ig --yes live start 123

# Monitor during the stream
ig live comments 123
ig live viewers 123

# End the broadcast
ig --yes --confirm "live:myshop" live end 123
```

## Raw Access

The `raw` group exposes all public `instagrapi.Client` methods directly. This is useful for methods not yet covered by curated commands:

```bash
# List all available client methods
ig raw methods

# See CLI coverage vs. instagrapi surface
ig raw coverage

# Inspect a method's parameters
ig raw schema user_info_by_username

# Call a read-only method with key=value arguments
ig raw call user_info_by_username --arg username=natgeo
```

Write and auth methods are blocked by default in raw mode. Only read-safe methods are allowed.

## Configuration

All state lives under `~/.config/ig-cli/`:

```
~/.config/ig-cli/
├── config.toml              # default account, safety policy overrides
├── sessions/
│   ├── myshop.json          # session cookies and state
│   └── personal.json
├── credentials/             # optional, for auto-re-login
│   ├── myshop.toml
│   └── personal.toml
└── safety_state.sqlite3     # circuit breaker, rate limiter state
```

### Environment Variables

| Variable | Effect |
|----------|--------|
| `IG_CLI_CONFIG_DIR` | Override config directory (default: `~/.config/ig-cli`) |

### Credential Files

Credentials are optional. Without them, `ig` uses saved sessions. When a session expires, it prompts interactively.

For unattended re-login, create `~/.config/ig-cli/credentials/<alias>.toml`:

```toml
username = "myshop_ig"
password_op_ref = "op://Vault/Instagram MyShop/password"     # 1Password reference
totp_op_ref = "op://Vault/Instagram MyShop/one-time-password" # optional
```

The CLI calls `op read` to resolve `op://` URIs at login time. You can also use a plaintext password (not recommended):

```toml
username = "myshop_ig"
password = "plaintext-password"
```

## Safety Layer

All Instagram API calls pass through a safety executor that protects against rate limiting, account bans, and accidental writes. The layer includes:

- **Circuit breaker** -- persistent across invocations; opens on consecutive failures or anti-abuse signals (429, challenge-required); auto-recovers after cooldown
- **Per-account rate limiting** -- token bucket per account and operation kind (read/write/auth)
- **Global request pacing** -- enforces minimum delay with jitter between all API calls
- **Retry with backoff** -- exponential backoff for transient failures; separate budgets for reads, writes, and auth
- **Write confirmation guard** -- interactive prompt for writes; typed confirmation token (`--confirm "scope:account"`) required for high-risk operations like deletes

Inspect safety state at any time:

```bash
ig safety status --account myshop
```

### Global Flags

| Flag | Effect |
|------|--------|
| `--yes` | Skip interactive write confirmation prompts |
| `--confirm "<scope>:<account>"` | Typed confirmation for high-risk writes |
| `--no-wait` | Fail fast instead of waiting for rate limit permits |
| `--unsafe` | Bypass the safety executor entirely |

See [SAFETY_SPEC.md](SAFETY_SPEC.md) for the full specification including default policy values, execution order, persistence model, and recovery rules.

## Requirements

- Python 3.12+
- [1Password CLI](https://developer.1password.com/docs/cli/) (optional, for `op://` credential references)

## Development

```bash
# Clone and install in development mode
git clone https://github.com/salmonumbrella/instagram-cli.git
cd instagram-cli
uv sync --group dev

# Run the CLI
uv run ig --help

# Run tests
uv run pytest

# Lint and format
uv run ruff check .
uv run ruff format .
```

## License

MIT
