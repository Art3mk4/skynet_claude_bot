# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

```bash
# Local development
pip install -r requirements.txt
python main.py

# Run tests
pytest -v                    # All tests
pytest test_handlers.py -v   # Specific test file
pytest -k test_function_name # Specific test

# Docker
docker compose up --build    # Build and start with tests
docker compose logs -f       # View logs
```

## Architecture

Async Telegram bot (aiogram 3.x) that proxies to Claude via OmniRoute (OpenAI-compatible API).

**Module Structure:**
- `main.py` — Bot initialization, middleware (log_updates, inject_claude), proxy fallback logic
- `handlers.py` — Non-command message handler: mention detection, text stripping, Claude response
- `commands.py` — All command handlers (`/start`, `/clear`, `/user_add`, etc.)
- `claude_client.py` — AsyncOpenAI client, conversation history (JSON), channel/user management
- `permissions.py` — User whitelist checks (ALLOWED_USERS env + users.json)
- `mentions.py` — Bot mention detection in groups/channels

**Key Design Patterns:**
- Middleware injects `ClaudeClient` instance into handler data dict
- Conversation history: `conversations/chat_{chat_id}.json`, max 20 messages (sliding window)
- Two user sources: `ALLOWED_USERS` env (immutable) + `users.json` (runtime)
- Two channel sources: active chats (auto-detected) + `channels.json` (manual)
- Proxy: Tor SOCKS5 with 10s timeout test, falls back to direct connection

**Mention Detection:**
- Primary: `message.entities` for MessageEntity mentions (most reliable)
- Fallback: regex search for `@username`, `skynet`, `скайнет` (case-insensitive)
- Text stripping removes mentions and leftover punctuation

## Bot Behavior

### Privacy Mode
For group/channel support, **Privacy Mode must be disabled** in @BotFather:
- `/mybots` → Select bot → Bot Settings → Group Privacy → **DISABLED**

### Private Chats
- Only users in `ALLOWED_USERS` can interact
- Bot responds to all messages from allowed users

### Group/Channel Chats
- Bot responds to **anyone** when mentioned (`@botname`, `skynet`, `скайнет`)
- `ALLOWED_USERS` does not apply here

**Important:** For channels, the bot only works through the **discussion group**, not the channel itself. Telegram bots cannot receive messages directly from channels - even if added as admin.

To use the bot in a channel:
1. Enable discussion group for your channel
2. Add bot as admin to the **discussion group**
3. Users must comment on posts and mention `@botname`, `skynet`, or `скайнет`

### Commands
- `/start` — Welcome message
- `/clear` — Clear conversation history
- `/chats` — List active chats with message counts
- `/channels` — List monitored channels (admin status)
- `/add_channel <id>` — Add a channel to monitored list
- `/remove_channel <id>` — Remove a channel from monitored list
- `/user_add <id>` — Add user to allowed list (private chat only)
- `/user_del <id>` — Remove user from allowed list (private chat only)
- `/user_list` — List allowed users (private chat only)
- `/help` — Show help

## Testing

- **85 automated tests** run on every container startup
- Tests cover: Claude client (14), Handlers (22), Middleware (8), Main (7), plus additional edge cases
- If tests fail, bot won't start
- Run locally: `pytest -v`

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TG_TOKEN` | Telegram Bot API token | Yes |
| `TG_PROXY` | SOCKS5 proxy URL (Tor) | No |
| `OMNIROUTE_BASE_URL` | OmniRoute API endpoint | Yes |
| `OMNIROUTE_MODEL` | Model to use | No (default: `kr/claude-sonnet-4.5`) |
| `OMNIROUTE_API_KEY` | OmniRoute API key | Yes |
| `ALLOWED_USERS` | Comma-separated user IDs | No |

## Important Notes

- `.env` is gitignored — copy from `.env.example`
- `conversations/` is gitignored — runtime data
- `venv/` is gitignored
- Uses `OMNIROUTE_API_KEY` and `OMNIROUTE_BASE_URL` (OpenAI-compatible wrapper)
- Bot name is "SkyNet"
- Channels require discussion group setup - bot cannot receive messages directly from channels
