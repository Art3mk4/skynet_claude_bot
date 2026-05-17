# CLAUDE.md

## Build & Run

```bash
# Local
pip install -r requirements.txt
python main.py

# Docker
docker compose up --build
```

## Architecture

This is a Telegram bot using **aiogram 3.x** (async) that proxies requests to an OmniRoute-compatible API (wrapping Claude).

**Core Components:**
- `main.py` — Entry point: init bot with aiogram, Tor proxy fallback, start polling
- `handlers.py` — Message handlers: `/start`, `/clear`, `/help`, `/chats`, and general message routing
- `claude_client.py` — Claude client via OpenAI-compatible API (AsyncOpenAI), conversation history management (JSON files)

**Key Design Patterns:**
- Async/await throughout (aiogram + aiohttp)
- Conversation history persisted to `conversations/chat_{chat_id}.json`
- Max 20 messages per conversation (sliding window)
- Proxy support: Tor SOCKS5 with direct connection fallback
- User whitelist via `ALLOWED_USERS` env var

**Mention Detection in Groups/Channels:**
- Checks `message.entities` for Telegram MessageEntity mentions (most reliable)
- Falls back to text search for `@username`, `skynet`, `скайнет`
- Supports mentions with or without @ symbol

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
- `/help` — Show help

## Testing

- **31 automated tests** run on every container startup
- Tests cover: Claude client (11), Handlers (13), Main (7)
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
