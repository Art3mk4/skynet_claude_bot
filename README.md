# SkyNet Telegram Bot

AI-powered Telegram bot using Claude via OmniRoute gateway.

## Features

- 🤖 Powered by Claude Sonnet 4.5 through OmniRoute
- 💬 Conversation history with context (last 20 messages)
- 🔒 Private chat support with full responses
- 👥 Group chat support (responds when mentioned)
- 🐳 Docker containerized
- 🔐 Tor/SOCKS5 proxy support for restricted networks
- 💾 Persistent conversation storage

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
ALLOWED_USERS=  # Optional, comma-separated user IDs
```

4. Build and run:
```bash
docker build -t skynet_bot .
docker run -d \
  --name skynet_bot \
  --network host \
  --env-file .env \
  --restart always \
  -v $(pwd)/conversations:/app/conversations \
  skynet_bot
```

## Usage

### Private Chat
Simply send any message to the bot - it will respond to everything.

### Group Chat
Mention the bot to get a response:
- `@bot_username your question`
- `skynet, help me with this`
- `скайнет, что это?`

### Commands
- `/start` - Start the bot
- `/clear` - Clear conversation history
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
| `ALLOWED_USERS` | Comma-separated user IDs | No | (all users) |

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

### Project Structure

```
claude_bot/
├── main.py              # Bot entry point
├── handlers.py          # Message handlers
├── claude_client.py     # OmniRoute API client
├── requirements.txt     # Python dependencies
├── Dockerfile          # Docker image
├── docker-compose.yml  # Docker Compose config
├── .env.example        # Environment template
└── conversations/      # Saved conversations
```

## OmniRoute

This bot uses [OmniRoute](https://github.com/diegosouzapw/OmniRoute) as an AI gateway. OmniRoute provides:
- Universal API proxy for 60+ AI providers
- Automatic fallback between providers
- Free and low-cost model routing
- OpenAI-compatible API

## Troubleshooting

### Bot doesn't respond
1. Check logs: `docker logs skynet_bot`
2. Verify Telegram API access: `curl https://api.telegram.org/bot<TOKEN>/getMe`
3. If blocked, configure Tor proxy

### Connection timeout
- Ensure Tor is running if using proxy
- Check `TG_PROXY` is correct (9150 for Tor Browser, 9050 for Tor service)

### OmniRoute errors
- Verify `OMNIROUTE_API_KEY` is valid
- Check `OMNIROUTE_BASE_URL` is accessible
- Test: `curl -H "Authorization: Bearer <KEY>" <BASE_URL>/models`

## License

MIT

## Contributing

Pull requests are welcome! For major changes, please open an issue first.

## Acknowledgments

- [aiogram](https://github.com/aiogram/aiogram) - Telegram Bot framework
- [OmniRoute](https://github.com/diegosouzapw/OmniRoute) - AI gateway
- [Anthropic Claude](https://www.anthropic.com/) - AI model
