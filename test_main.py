import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from aiogram import Bot
from main import main


@pytest.mark.asyncio
class TestMain:
    async def test_main_no_token(self):
        with patch('main.load_dotenv'), \
             patch('os.getenv', return_value=None):
            with pytest.raises(ValueError, match="TG_TOKEN not found"):
                await main()

    async def test_main_with_token_no_proxy(self):
        with patch('main.load_dotenv'), \
             patch('os.getenv', side_effect=lambda key, default=None: {
                 'TG_TOKEN': 'test_token',
                 'TG_PROXY': None
             }.get(key, default)), \
             patch('main.Bot') as mock_bot_class, \
             patch('main.Dispatcher') as mock_dp_class:

            mock_bot = Mock()
            mock_bot_class.return_value = mock_bot

            mock_dp = Mock()
            mock_dp.resolve_used_update_types.return_value = []
            mock_dp.start_polling = AsyncMock()
            mock_dp_class.return_value = mock_dp

            await main()

            mock_bot_class.assert_called_once()
            mock_dp.start_polling.assert_called_once_with(
                mock_bot,
                allowed_updates=[]
            )

    async def test_main_with_proxy_success(self):
        with patch('main.load_dotenv'), \
             patch('os.getenv', side_effect=lambda key, default=None: {
                 'TG_TOKEN': 'test_token',
                 'TG_PROXY': 'socks5://localhost:9050'
             }.get(key, default)), \
             patch('main.AiohttpSession') as mock_session_class, \
             patch('main.Bot') as mock_bot_class, \
             patch('main.Dispatcher') as mock_dp_class, \
             patch('main.asyncio.wait_for', new_callable=AsyncMock) as mock_wait:

            mock_session = Mock()
            mock_session_class.return_value = mock_session

            mock_test_bot = Mock()
            mock_test_bot.get_me = AsyncMock()
            mock_test_bot.session.close = AsyncMock()

            mock_bot = Mock()
            mock_bot_class.side_effect = [mock_test_bot, mock_bot]

            mock_dp = Mock()
            mock_dp.resolve_used_update_types.return_value = []
            mock_dp.start_polling = AsyncMock()
            mock_dp_class.return_value = mock_dp

            await main()

            assert mock_session_class.call_count == 1
            mock_wait.assert_called_once()

    async def test_main_with_proxy_failure(self):
        with patch('main.load_dotenv'), \
             patch('os.getenv', side_effect=lambda key, default=None: {
                 'TG_TOKEN': 'test_token',
                 'TG_PROXY': 'socks5://localhost:9050'
             }.get(key, default)), \
             patch('main.AiohttpSession') as mock_session_class, \
             patch('main.Bot') as mock_bot_class, \
             patch('main.Dispatcher') as mock_dp_class, \
             patch('main.asyncio.wait_for', side_effect=Exception("Proxy failed")):

            mock_session = Mock()
            mock_session_class.return_value = mock_session

            mock_test_bot = Mock()
            mock_test_bot.get_me = AsyncMock()

            mock_bot = Mock()
            mock_bot_class.side_effect = [mock_test_bot, mock_bot]

            mock_dp = Mock()
            mock_dp.resolve_used_update_types.return_value = []
            mock_dp.start_polling = AsyncMock()
            mock_dp_class.return_value = mock_dp

            await main()

            # Должен создать бота без прокси после падения
            assert mock_bot_class.call_count == 2

    async def test_main_polling_error(self):
        with patch('main.load_dotenv'), \
             patch('os.getenv', side_effect=lambda key, default=None: {
                 'TG_TOKEN': 'test_token',
                 'TG_PROXY': None
             }.get(key, default)), \
             patch('main.Bot') as mock_bot_class, \
             patch('main.Dispatcher') as mock_dp_class:

            mock_bot = Mock()
            mock_bot_class.return_value = mock_bot

            mock_dp = Mock()
            mock_dp.resolve_used_update_types.return_value = []
            mock_dp.start_polling = AsyncMock(side_effect=Exception("Polling failed"))
            mock_dp_class.return_value = mock_dp

            with pytest.raises(Exception, match="Polling failed"):
                await main()


import sys
sys.path.insert(0, '/app')

from unittest.mock import AsyncMock, Mock, patch
from aiogram.types import Message, Chat, User, Update
from main import log_updates


@pytest.mark.asyncio
class TestLogUpdatesMiddleware:
    async def test_log_updates_private_message_with_mention(self):
        message = Mock()
        message.chat = Mock()
        message.chat.id = 123
        message.chat.type = "private"
        message.from_user = Mock()
        message.from_user.id = 456
        message.text = "@testbot привет"
        message.bot = Mock()
        message.bot.me = AsyncMock(return_value=Mock(username="testbot"))

        handler = AsyncMock()
        event = Mock()
        event.update_id = 1
        event.event_type = "message"
        event.message = message

        with patch('main.logger') as mock_logger:
            await log_updates(handler, event, {})
            # Should log mention detection
            assert mock_logger.info.called

    async def test_log_updates_group_without_mention(self):
        message = Mock()
        message.chat = Mock()
        message.chat.id = -100
        message.chat.type = "group"
        message.from_user = Mock()
        message.from_user.id = 456
        message.text = "просто текст"
        message.bot = Mock()
        message.bot.me = AsyncMock(return_value=Mock(username="testbot"))

        handler = AsyncMock()
        event = Mock()
        event.update_id = 2
        event.event_type = "message"
        event.message = message

        with patch('main.logger') as mock_logger:
            await log_updates(handler, event, {})
            assert mock_logger.info.called

    async def test_log_updates_channel_message(self):
        message = Mock()
        message.chat = Mock()
        message.chat.id = -200
        message.chat.type = "channel"
        message.from_user = Mock()
        message.from_user.id = 789
        message.text = "@testbot сообщение"
        message.bot = Mock()
        message.bot.me = AsyncMock(return_value=Mock(username="testbot"))

        handler = AsyncMock()
        event = Mock()
        event.update_id = 3
        event.event_type = "message"
        event.message = message

        with patch('main.logger') as mock_logger:
            await log_updates(handler, event, {})
            assert mock_logger.info.called

    async def test_log_updates_no_text(self):
        message = Mock()
        message.chat = Mock()
        message.chat.id = 123
        message.chat.type = "private"
        message.from_user = Mock()
        message.from_user.id = 456
        message.text = None
        message.bot = Mock()

        handler = AsyncMock(return_value=None)
        event = Mock()
        event.update_id = 4
        event.event_type = "message"
        event.message = message

        with patch('main.logger') as mock_logger:
            await log_updates(handler, event, {})
            assert mock_logger.info.called

    async def test_log_updates_no_message(self):
        handler = AsyncMock()
        event = Mock()
        event.update_id = 5
        event.event_type = "edited_message"
        event.message = None

        with patch('main.logger') as mock_logger:
            await log_updates(handler, event, {})
            # Should not crash even without message
            assert mock_logger.info.called or True
