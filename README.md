# SkyNet Telegram Bot

<div align="center">

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Tests](https://img.shields.io/badge/tests-31-passing-brightgreen.svg)

AI-powered Telegram bot using Claude Sonnet 4.5 through OmniRoute gateway.

</div>

## ✨ Features

- **Claude Sonnet 4.5** via OmniRoute AI gateway
- **Conversation context** - remembers last 20 messages per chat
- **Privacy-first** - user whitelist for private chats
- **Group support** - responds to mentions (no privacy mode needed)
- **Channel integration** - works through discussion groups
- **Tor support** - SOCKS5 proxy with automatic fallback
- **Docker-ready** - containerized deployment
- **Tested** - 31 automated tests on startup

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Telegram Bot Token ([@BotFather](https://t.me/BotFather))
- OmniRoute API access
- (Optional) Tor/SOCKS5 proxy for restricted networks

### Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd claude_bot
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Start with Docker**
   ```bash
   docker compose up -d
   ```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TG_TOKEN` | Telegram Bot API token | Yes |
| `OMNIROUTE_BASE_URL` | OmniRoute API endpoint | Yes |
| `OMNIROUTE_API_KEY` | OmniRoute API key | Yes |
| `TG_PROXY` | SOCKS5 proxy URL (Tor) | No |
| `OMNIROUTE_MODEL` | Model to use | No (default: `kr/claude-sonnet-4.5`) |
| `ALLOWED_USERS` | Comma-separated user IDs for private chats | No |

## 📋 Bot Setup Guide

### 1. Disable Privacy Mode

For the bot to work in groups and channels, **Privacy Mode must be disabled**:

1. Send `/mybots` to @BotFather
2. Select your bot → `Bot Settings` → `Group Privacy`
3. Set to **DISABLED**

### 2. Channel Setup (Important!)

Telegram bots cannot receive messages directly from channels. To use the bot with a channel:

1. Enable discussion group for your channel
2. Add bot as admin to the **discussion group**
3. Users comment on posts and mention: `@botname`, `skynet`, or `скайнет`

**The bot only works through the discussion group, not the channel itself.**

## 💬 Usage

### Private Chats
- Only users in `ALLOWED_USERS` can interact
- Bot responds to all messages from allowed users

### Group/Channel Discussion Groups
- Bot responds to **anyone** when mentioned
- Mention formats: `@botname`, `skynet`, `скайнет`

### Available Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Show help |
| `/clear` | Clear conversation history |
| `/chats` | List active chats with message counts |
| `/channels` | List monitored channels (admin status) |
| `/add_channel <id>` | Add channel to monitored list |
| `/remove_channel <id>` | Remove channel from monitored list |

**Note:** Channel management commands (`/channels`, `/add_channel`, `/remove_channel`) only work in private chats.

## 🛠️ Development

### Local Setup

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Running Tests

```bash
pytest -v
```

Tests run automatically on Docker startup. If tests fail, the bot won't start.

### Project Structure

```
claude_bot/
├── main.py              # Bot entry point with middleware
├── handlers.py          # Message handlers and commands
├── claude_client.py     # OmniRoute API client
├── entrypoint.sh        # Docker entrypoint with test runner
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker image definition
├── docker-compose.yml   # Docker Compose configuration
├── test_*.py            # Test files (31 tests)
├── .env.example         # Environment template
└── conversations/       # Saved conversations (persistent)
```

## 🧪 Testing

The bot includes comprehensive test coverage:

- **11 tests** for Claude client (API, conversation management)
- **13 tests** for handlers (commands, mentions, permissions)
- **7 tests** for main (proxy, initialization, error handling)

All tests run automatically on container startup using pytest.

## 🌐 OmniRoute

This bot uses [OmniRoute](https://github.com/diegosouzapw/OmniRoute) as an AI gateway. OmniRoute provides:

- Universal API proxy for 60+ AI providers
- Automatic fallback between providers
- Free and low-cost model routing
- OpenAI-compatible API

## 🐳 Docker Deployment

```bash
# Build and run
docker compose up -d

# View logs
docker compose logs -f

# Restart bot
docker compose restart

# Stop bot
docker compose down
```

## 🔧 Troubleshooting

### Bot doesn't respond in groups

1. Verify Privacy Mode is **disabled** in @BotFather
2. Remove and re-add the bot to the group
3. Ensure bot is mentioned: `@bot_username message`
4. Check logs: `docker compose logs`

### Bot doesn't respond in channel comments

**Important:** Telegram bots cannot receive messages from channels directly.

1. Verify your channel has a discussion group enabled
2. Bot must be admin in the **discussion group**
3. Check Privacy Mode is **disabled**
4. Ensure you're mentioning the bot in discussion group comments

### Connection timeout

- Ensure Tor is running if using proxy
- Check `TG_PROXY` is correct (9150 for Tor Browser, 9050 for Tor service)
- Verify proxy: `curl --socks5 127.0.0.1:9150 https://api.telegram.org`

### OmniRoute errors

- Verify `OMNIROUTE_API_KEY` is valid
- Check `OMNIROUTE_BASE_URL` is accessible
- Test: `curl -H "Authorization: Bearer <KEY>" <BASE_URL>/models`

## 📄 License

MIT

## 👥 Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.
