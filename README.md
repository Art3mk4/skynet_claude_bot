# SkyNet Telegram Bot

<div align="center">

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Tests](https://img.shields.io/badge/tests-51-passing-brightgreen.svg)

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
- **Tested** - 51 automated tests on startup

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

3. **Start with Docker Compose (recommended)**
   ```bash
   docker compose up -d
   ```

   **Or using docker build directly:**
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

### Environment Variables

Create `.env` file with your credentials:

```env
# Telegram Bot Token (from @BotFather)
TG_TOKEN=your_telegram_bot_token

# SOCKS5 proxy URL (Tor) - optional, leave empty if not needed
TG_PROXY=socks5://127.0.0.1:9150

# OmniRoute API endpoint
OMNIROUTE_BASE_URL=https://your-omniroute-instance/v1

# OmniRoute API key
OMNIROUTE_API_KEY=your_omniroute_api_key

# Model to use (optional, defaults to kr/claude-sonnet-4.5)
OMNIROUTE_MODEL=kr/claude-sonnet-4.5

# User IDs for private chat access (comma-separated, optional)
# Example: ALLOWED_USERS=123456789,987654321
ALLOWED_USERS=
```

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
| `/start` | Start the bot and see welcome message |
| `/help` | Show help message |
| `/clear` | Clear conversation history for current chat |
| `/chats` | List all active chats with message counts |
| `/channels` | List monitored channels where bot is admin |
| `/add_channel <id>` | Add a channel to monitored list |
| `/remove_channel <id>` | Remove a channel from monitored list |

### User Management (Private Chat Only)

| Command | Description |
|---------|-------------|
| `/user_list` | List allowed users |
| `/user_add <id>` | Add user to allowed list |
| `/user_del <id>` | Remove user from allowed list |

**Note:** Channel management and user management commands only work in private chats.

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
├── test_*.py            # Test files (51 tests)
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
