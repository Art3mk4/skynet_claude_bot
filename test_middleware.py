import pytest
from unittest.mock import AsyncMock, Mock, patch
from main import log_updates


@pytest.mark.asyncio
class TestLogUpdatesMiddleware:
    async def test_log_updates_private_message(self):
        message = Mock()
        message.chat = Mock()
        message.chat.id = 123
        message.chat.type = "private"
        message.from_user = Mock()
        message.from_user.id = 456
        message.text = "hello"

        handler = AsyncMock()
        event = Mock()
        event.update_id = 1
        event.event_type = "message"
        event.message = message

        with patch('main.logger') as mock_logger:
            await log_updates(handler, event, {})
            handler.assert_called_once_with(event, {})
            assert mock_logger.info.called

    async def test_log_updates_group_message(self):
        message = Mock()
        message.chat = Mock()
        message.chat.id = -100
        message.chat.type = "group"
        message.from_user = Mock()
        message.from_user.id = 456
        message.text = "hello bot"

        handler = AsyncMock()
        event = Mock()
        event.update_id = 2
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

        handler = AsyncMock()
        event = Mock()
        event.update_id = 3
        event.event_type = "message"
        event.message = message

        with patch('main.logger') as mock_logger:
            await log_updates(handler, event, {})
            assert mock_logger.info.called

    async def test_log_updates_no_message(self):
        handler = AsyncMock()
        event = Mock()
        event.update_id = 4
        event.event_type = "edited_message"
        event.message = None

        with patch('main.logger'):
            await log_updates(handler, event, {})
            handler.assert_called_once_with(event, {})

    async def test_log_updates_middleware_error(self):
        message = Mock()
        message.chat = Mock()
        message.chat.id = 123
        message.chat.type = "private"
        message.from_user = Mock()
        message.from_user.id = 456
        message.text = "test"

        handler = AsyncMock()
        event = Mock()
        event.update_id = 5
        event.event_type = "message"
        event.message = message

        # Make logger.info raise
        with patch('main.logger', side_effect=Exception("logger error")):
            # Should not crash
            await log_updates(handler, event, {})
