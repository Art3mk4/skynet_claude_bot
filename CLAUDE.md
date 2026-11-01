# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

```bash
# Local development
pip install -r requirements.txt
pip install -r requirements-test.txt
python main.py

# Run tests
pytest -v                    # All tests
pytest test_handlers.py -v   # Specific test file
pytest -k test_function_name # Specific test

# Docker (tests run automatically before the bot starts)
docker compose up --build
docker compose logs -f
```

Tests also run inside the container via `entrypoint.sh` (`TEST_MODE=1 pytest`) before `main.py` starts — if tests fail, the container exits and the bot does not start. `TEST_MODE=1` makes `ClaudeClient.__init__` delete `conversations/users.json` on startup, so tests always start from a clean allowed-users state.

## Architecture

Async Telegram bot (aiogram 3.x) that proxies to Claude via OmniRoute (OpenAI-compatible API, `AsyncOpenAI` client pointed at `OMNIROUTE_BASE_URL`).

**Module Structure:**
- `main.py` — Bot init, `log_updates` logging middleware, Tor proxy connectivity test with fallback
- `handlers.py` — Catch-all non-command message handler: permission/mention checks, mention stripping, Claude call
- `commands.py` — All command handlers (`/start`, `/clear`, `/chats`, `/channels`, `/user_add`, etc.)
- `claude_client.py` — `AsyncOpenAI` wrapper + conversation history, channel list, and user list persistence (JSON files under `conversations/`)
- `permissions.py` — `is_allowed_user()` function and `AllowedUserFilter` aiogram filter
- `mentions.py` — Bot mention detection in groups/channels

**`ClaudeClient` is a single shared instance:**
`main()` constructs exactly one `ClaudeClient()` and registers it as aiogram workflow data (`dp['claude'] = ClaudeClient()`), so it's injected by name into every handler and filter that declares a `claude: ClaudeClient` parameter — including `permissions.AllowedUserFilter` and `permissions.is_allowed_user(user_id, claude)`, which now take the shared instance instead of constructing their own. State changes (e.g. `/user_add`) are visible immediately because everything reads/writes the same in-memory dicts (`conversations`, `monitored_channels`, `allowed_users`), backed by the JSON files under `conversations/` only as persistence, not as a source of truth re-read per request.

**Permission model (two different enforcement styles coexist):**
- `permissions.is_allowed_user(user_id, claude)` and `AllowedUserFilter.__call__(self, message, claude)` both take the shared `ClaudeClient` via aiogram DI (see above) — they never construct their own.
- `/clear`, `/help`, `/chats`, `/channels`, `/add_channel`, `/remove_channel` use the `AllowedUserFilter()` aiogram filter — unauthorized users get no response at all (filter just doesn't match).
- `/user_add`, `/user_del`, `/user_list` go through `commands._require_private_allowed_user(message, claude)` (private-chat check, then `is_allowed_user`) so they can send an explicit rejection message instead of silently ignoring.
- `handlers.py`'s catch-all handler applies checks in this order: private chat → must be in `is_allowed_user`; group/channel → must be a mention (`is_mention`) *and* the sender must be in `is_allowed_user` (unlike the README's "responds to anyone when mentioned" framing, the allowed-user check still applies — `ALLOWED_USERS` gates who can trigger a response everywhere, mentions only additionally gate groups/channels).
- Users come from two independent sources merged via `is_allowed_user()`/`get_allowed_users()`: the immutable `ALLOWED_USERS` env var and the runtime-editable `conversations/users.json`.

**Conversation history:**
- Stored per chat in `conversations/chat_{chat_id}.json`, capped at the last 20 messages (sliding window applied after each turn).
- Each stored message carries `role`/`content` plus non-standard `user_id`/`user_name` metadata, and the whole list is spread directly into the OpenAI `messages=[...]` payload alongside a system prompt — the extra keys ride along in the request but are not used by the API.
- Async file writes go through a per-chat `asyncio.Lock` (`_conversation_locks`, LRU-capped at 100 entries) to avoid concurrent-write corruption; `channels.json`/`users.json` each have their own single lock.

**Mention Detection (`mentions.py`):**
- Primary: `message.entities` for `mention`-type entities (most reliable, avoids false positives from bot username substrings).
- Fallback: case-insensitive substring/word match for `@username`, bare username, `skynet`, `скайнет`.
- `handlers._strip_mentions` then removes the mention/alias text and leftover punctuation before sending to Claude; an empty result after stripping short-circuits to a canned reply instead of calling the API.

**Proxy handling (`main.py`):** if `TG_PROXY` is set, a throwaway `Bot`/`AiohttpSession` is used to call `get_me()` with a 10s timeout as a connectivity probe; on failure it logs a warning and falls back to a direct (no-proxy) session rather than failing startup.

## Bot Behavior

### Privacy Mode
For group/channel support, **Privacy Mode must be disabled** in @BotFather:
- `/mybots` → Select bot → Bot Settings → Group Privacy → **DISABLED**

### Channels
**Important:** the bot only works through a channel's **discussion group**, not the channel itself — Telegram bots cannot receive messages directly from channels even as admin. To wire one up: enable the discussion group, add the bot as admin there, and have users mention `@botname`/`skynet`/`скайнет` in comments.

### Commands
- `/start`, `/help` — welcome / help text
- `/clear` — clear conversation history for the current chat
- `/chats` — list active chats with message counts (chat type resolved via `bot.get_chat`, with an ID-sign heuristic fallback if that call fails)
- `/channels` — list manually-added channels plus any active chat where the bot is admin
- `/add_channel <id>` / `/remove_channel <id>` — manage the monitored-channels list
- `/user_add <id>` / `/user_del <id>` / `/user_list` — manage `users.json`; private chat only

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TG_TOKEN` | Telegram Bot API token | Yes |
| `TG_PROXY` | SOCKS5 proxy URL (Tor), falls back to direct if unreachable | No |
| `OMNIROUTE_BASE_URL` | OmniRoute API endpoint | Yes |
| `OMNIROUTE_MODEL` | Model to use | No (default: `kr/claude-sonnet-4.5`) |
| `OMNIROUTE_API_KEY` | OmniRoute API key (must not start with `your_`, or `ClaudeClient.__init__` raises) | Yes |
| `ALLOWED_USERS` | Comma-separated user IDs | No |

## Important Notes

- `.env`, `conversations/`, and `venv/` are gitignored.
- `conversations/` is a Docker volume mount (`docker-compose.yml`) — persists across container rebuilds.
- Bot name is "SkyNet"; default `ParseMode` is Markdown (set in `main.py`), individual replies override to HTML where they build `<code>`/`&lt;&gt;` snippets.
