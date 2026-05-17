# SkyNet Telegram Bot

AI-powered Telegram bot using Claude via OmniRoute gateway.

## Features

- 🤖 Powered by Claude Sonnet 4.5 through OmniRoute
- 💬 Conversation history with context (last 20 messages)
- 🔒 Private chat support with full responses
- 👥 Group chat support (responds when mentioned)
- 📢 Channel comments support (responds when mentioned)
- 🐳 Docker containerized with automated testing
- 🔐 Tor/SOCKS5 proxy support for restricted networks
- 💾 Persistent conversation storage
- ✅ 31 automated tests run on startup

## Prerequisites

- Docker
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- OmniRoute API access
- (Optional) Tor/SOCKS5 proxy for Telegram API access

## Quick Start

1. Clone the repository:
```bash
git clone <your-repo-url>
cd claude_bot
```

2. Create `.env` file:
```bash
cp .env.example .env
```

3. Edit `.env` with your credentials:
```env
TG_TOKEN=your_telegram_bot_token
TG_PROXY=socks5://127.0.0.1:9150  # Optional, for Tor
OMNIROUTE_BASE_URL=https://your-omniroute-instance/v1
OMNIROUTE_MODEL=kr/claude-sonnet-4.5
OMNIROUTE_API_KEY=your_omniroute_api_key
ALLOWED_USERS=123456789  # Your Telegram user ID for private chats
```

4. Build and run:
```bash
docker build -t skynet_claude_bot .
docker run -d \
  --name skynet_claude_bot \
  --network host \
  --env-file .env \
  --restart always \
  -v $(pwd)/conversations:/app/conversations \
  skynet_claude_bot
```

## Bot Configuration

### Privacy Mode
For the bot to work in groups and channels, you must disable Privacy Mode in @BotFather:
1. Send `/mybots` to @BotFather
2. Select your bot
3. Go to `Bot Settings` → `Group Privacy`
4. Set to **DISABLED**

### Channel Setup

**Important:** Telegram bots cannot receive messages directly from channels. To make the bot respond in channels, you need to set up a **discussion group**.

1. Create or select a discussion group for your channel
2. Add the bot as an administrator to the **discussion group**
3. Add the bot as an administrator to the **channel** (optional, only if you want to use /channels command)
4. Give the bot permissions to read and send messages in the discussion group

**How it works:**
- Bot receives messages from the **discussion group**, not the channel itself
- Users must comment on channel posts and mention `@botname`, `skynet`, or `скайнет`
- Bot will respond only to mentions in the discussion group comments

## Usage

### Private Chat
The bot responds only to users listed in `ALLOWED_USERS`. Simply send any message.

### Group Chat
The bot responds to **anyone** when mentioned (ignores `ALLOWED_USERS` in groups):
- `@bot_username your question`
- `skynet, help me with this`
- `скайнет, что это?`

### Channel Comments

**Note:** Channel comments here refers to comments in the **discussion group** associated with your channel.

The bot responds to **anyone** when mentioned in the discussion group:
- `@bot_username your question`
- `skynet, help me with this`
- `скайнет, что это?`

**Important:** If your channel doesn't have a discussion group enabled, the bot cannot receive or respond to messages from that channel.

### Commands
- `/start` - Start the bot and see welcome message
- `/clear` - Clear conversation history for current chat
- `/chats` - List all active chats with message counts
- `/channels` - List monitored channels where bot is admin
- `/add_channel <id>` - Add a channel to monitored list
- `/remove_channel <id>` - Remove a channel from monitored list
- `/help` - Show help message

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `TG_TOKEN` | Telegram Bot API token | Yes | - |
| `TG_PROXY` | SOCKS5 proxy URL | No | - |
| `OMNIROUTE_BASE_URL` | OmniRoute API endpoint | Yes | - |
| `OMNIROUTE_MODEL` | Model to use | No | `kr/claude-sonnet-4.5` |
| `OMNIROUTE_API_KEY` | OmniRoute API key | Yes | - |
| `ALLOWED_USERS` | User IDs for private chat access | No | (all users) |

**Note:** `ALLOWED_USERS` only applies to private chats. In groups and channel discussion groups, the bot responds to anyone when mentioned.

### Using with Tor

If Telegram API is blocked in your region:

1. Install Tor Browser or Tor service
2. Set `TG_PROXY=socks5://127.0.0.1:9150` (Tor Browser) or `socks5://127.0.0.1:9050` (Tor service)
3. Restart the bot

**Note:** The bot automatically falls back to direct connection if proxy is unavailable.

## Development

### Local Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Running Tests

```bash
pytest -v
```

Tests are automatically run when the Docker container starts. If tests fail, the bot won't start.

### Project Structure

```
claude_bot/
├── main.py              # Bot entry point with middleware
├── handlers.py          # Message handlers and commands
├── claude_client.py     # OmniRoute API client
├── entrypoint.sh        # Docker entrypoint with test runner
├── requirements.txt     # Python dependencies
├── Dockerfile          # Docker image with pytest
├── test_*.py           # Test files (31 tests)
├── .env.example        # Environment template
└── conversations/      # Saved conversations (persistent)
```

## Testing

The bot includes comprehensive test coverage:
- **11 tests** for Claude client (API, conversation management)
- **13 tests** for handlers (commands, mentions, permissions)
- **7 tests** for main (proxy, initialization, error handling)

All tests run automatically on container startup using pytest.

## OmniRoute

This bot uses [OmniRoute](https://github.com/diegosouzapw/OmniRoute) as an AI gateway. OmniRoute provides:
- Universal API proxy for 60+ AI providers
- Automatic fallback between providers
- Free and low-cost model routing
- OpenAI-compatible API

## Troubleshooting

### Bot doesn't respond in groups
1. Check Privacy Mode is **disabled** in @BotFather
2. Remove bot from group and add again
3. Ensure bot is mentioned: `@bot_username message`
4. Check logs: `docker logs skynet_claude_bot`

### Bot doesn't respond in channel comments

**Important:** Telegram bots cannot receive messages from channels directly. The bot only works through the **discussion group**.

1. Verify your channel has a discussion group enabled (Settings → Group → Discussion group)
2. Bot must be admin in the **discussion group** (not just the channel)
3. Check Privacy Mode is **disabled** in @BotFather
4. Check logs for incoming messages: `docker logs skynet_claude_bot --tail 50`
5. Ensure you're mentioning the bot in discussion group comments: `@botname message`

If your channel doesn't have a discussion group, the bot cannot receive messages from it.

### Connection timeout
- Ensure Tor is running if using proxy
- Check `TG_PROXY` is correct (9150 for Tor Browser, 9050 for Tor service)
- Verify proxy: `curl --socks5 127.0.0.1:9150 https://api.telegram.org`

### OmniRoute errors
- Verify `OMNIROUTE_API_KEY` is valid
- Check `OMNIROUTE_BASE_URL` is accessible
- Test: `curl -H "Authorization: Bearer <KEY>" <BASE_URL>/models`

### Tests failing on startup
- Check logs: `docker logs skynet_claude_bot`
- Run tests locally: `pytest -v`
- Ensure all dependencies are installed

## License

MIT

## Contributing

Pull requests are welcome! For major changes, please open an issue first.

## Acknowledgments

- [aiogram](https://github.com/aiogram/aiogram) - Telegram Bot framework
- [OmniRoute](https://github.com/diegosouzapw/OmniRoute) - AI gateway
- [Anthropic Claude](https://www.anthropic.com/) - AI model
