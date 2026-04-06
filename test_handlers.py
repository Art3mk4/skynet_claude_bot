import pytest
from unittest.mock import AsyncMock, Mock, patch
from aiogram.types import Message, Chat, User
from handlers import is_allowed_user, is_mention, router


class TestIsAllowedUser:
    def test_no_allowed_users_env(self):
        with patch('os.getenv', return_value=''):
            assert is_allowed_user(123) is True
            assert is_allowed_user(456) is True

    def test_with_allowed_users(self):
        with patch('os.getenv', return_value='123,456,789'):
            assert is_allowed_user(123) is True
            assert is_allowed_user(456) is True
            assert is_allowed_user(999) is False


@pytest.mark.asyncio
class TestIsMention:
    async def test_no_text(self):
        message = Mock(spec=Message)
        message.text = None
        assert await is_mention(message) is False

    async def test_mention_with_username(self):
        message = Mock(spec=Message)
        message.text = "@testbot привет"
        bot_info = Mock()
        bot_info.username = "testbot"
        message.bot = Mock()
        message.bot.me = AsyncMock(return_value=bot_info)
        assert await is_mention(message) is True

    async def test_mention_skynet_english(self):
        message = Mock(spec=Message)
        message.text = "skynet, помоги"
        bot_info = Mock()
        bot_info.username = "testbot"
        message.bot = Mock()
        message.bot.me = AsyncMock(return_value=bot_info)
        assert await is_mention(message) is True

    async def test_mention_skynet_russian(self):
        message = Mock(spec=Message)
        message.text = "скайнет расскажи"
        bot_info = Mock()
        bot_info.username = "testbot"
        message.bot = Mock()
        message.bot.me = AsyncMock(return_value=bot_info)
        assert await is_mention(message) is True

    async def test_no_mention(self):
        message = Mock(spec=Message)
        message.text = "просто текст"
        bot_info = Mock()
        bot_info.username = "testbot"
        message.bot = Mock()
        message.bot.me = AsyncMock(return_value=bot_info)
        assert await is_mention(message) is False


@pytest.mark.asyncio
class TestHandlers:
    async def test_cmd_start_allowed_user(self):
        message = AsyncMock()
        message.from_user = Mock()
        message.from_user.id = 123
        message.answer = AsyncMock()

        with patch('handlers.is_allowed_user', return_value=True):
            from handlers import cmd_start
            await cmd_start(message)
            message.answer.assert_called_once()
            assert "SkyNet" in message.answer.call_args[0][0]

    async def test_cmd_start_not_allowed(self):
        message = AsyncMock()
        message.from_user = Mock()
        message.from_user.id = 999
        message.answer = AsyncMock()

        with patch('handlers.is_allowed_user', return_value=False):
            from handlers import cmd_start
            await cmd_start(message)
            message.answer.assert_called_once_with("У вас нет доступа к этому боту")

    async def test_cmd_clear(self):
        message = AsyncMock()
        message.from_user = Mock()
        message.from_user.id = 123
        message.chat = Mock()
        message.chat.id = 456
        message.answer = AsyncMock()

        with patch('handlers.is_allowed_user', return_value=True), \
             patch('handlers.claude.clear_history') as mock_clear:
            from handlers import cmd_clear
            await cmd_clear(message)
            mock_clear.assert_called_once_with(456)
            message.answer.assert_called_once_with("История диалога очищена")

    async def test_handle_message_private_chat_allowed_user(self):
        message = AsyncMock()
        message.from_user = Mock()
        message.from_user.id = 123
        message.from_user.full_name = "Test User"
        message.chat = Mock()
        message.chat.id = 456
        message.chat.type = 'private'
        message.chat.do = AsyncMock()
        message.text = "привет"
        message.answer = AsyncMock()

        bot_info = Mock()
        bot_info.username = "testbot"
        message.bot = Mock()
        message.bot.me = AsyncMock(return_value=bot_info)

        with patch('handlers.is_allowed_user', return_value=True), \
             patch('handlers.claude.get_response', return_value="Привет!") as mock_response:
            from handlers import handle_message
            await handle_message(message)
            mock_response.assert_called_once_with(456, "привет", "Test User")
            message.answer.assert_called_once()

    async def test_handle_message_private_chat_not_allowed_user(self):
        message = AsyncMock()
        message.from_user = Mock()
        message.from_user.id = 999
        message.from_user.full_name = "Test User"
        message.chat = Mock()
        message.chat.id = 456
        message.chat.type = 'private'
        message.text = "привет"
        message.answer = AsyncMock()

        with patch('handlers.is_allowed_user', return_value=False):
            from handlers import handle_message
            await handle_message(message)
            message.answer.assert_not_called()

    async def test_handle_message_group_with_mention(self):
        message = AsyncMock()
        message.from_user = Mock()
        message.from_user.id = 999
        message.from_user.full_name = "Test User"
        message.chat = Mock()
        message.chat.id = 789
        message.chat.type = 'group'
        message.chat.do = AsyncMock()
        message.text = "@testbot привет"
        message.answer = AsyncMock()

        bot_info = Mock()
        bot_info.username = "testbot"
        message.bot = Mock()
        message.bot.me = AsyncMock(return_value=bot_info)

        with patch('handlers.claude.get_response', return_value="Привет!"):
            from handlers import handle_message
            await handle_message(message)
            message.answer.assert_called_once()

    async def test_handle_message_group_without_mention(self):
        message = AsyncMock()
        message.from_user = Mock()
        message.from_user.id = 123
        message.chat = Mock()
        message.chat.id = 789
        message.chat.type = 'group'
        message.text = "просто текст"
        message.answer = AsyncMock()

        bot_info = Mock()
        bot_info.username = "testbot"
        message.bot = Mock()
        message.bot.me = AsyncMock(return_value=bot_info)

        from handlers import handle_message
        await handle_message(message)
        message.answer.assert_not_called()

    async def test_handle_message_long_response(self):
        message = AsyncMock()
        message.from_user = Mock()
        message.from_user.id = 123
        message.from_user.full_name = "Test User"
        message.chat = Mock()
        message.chat.id = 456
        message.chat.type = 'private'
        message.chat.do = AsyncMock()
        message.text = "расскажи много"
        message.answer = AsyncMock()

        bot_info = Mock()
        bot_info.username = "testbot"
        message.bot = Mock()
        message.bot.me = AsyncMock(return_value=bot_info)

        long_response = "x" * 5000

        with patch('handlers.is_allowed_user', return_value=True), \
             patch('handlers.claude.get_response', return_value=long_response):
            from handlers import handle_message
            await handle_message(message)
            assert message.answer.call_count == 2
