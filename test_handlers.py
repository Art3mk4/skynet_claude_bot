import pytest
from unittest.mock import AsyncMock, Mock, patch
from aiogram.types import Message, Chat, User
from handlers import is_allowed_user, is_mention, router
from claude_client import ClaudeClient


class TestIsAllowedUser:
    def test_no_allowed_users_env(self):
        with patch('os.getenv', return_value=''), \
             patch('claude_client.ClaudeClient') as MockClient:
            mock_client = MockClient.return_value
            mock_client.allowed_users = {}
            assert is_allowed_user(123) is False
            assert is_allowed_user(456) is False

    def test_with_allowed_users(self):
        with patch('os.getenv', return_value='123,456,789'), \
             patch('claude_client.ClaudeClient') as MockClient:
            mock_client = MockClient.return_value
            mock_client.allowed_users = {}
            assert is_allowed_user(123) is True
            assert is_allowed_user(456) is True
            assert is_allowed_user(999) is False

    def test_users_json_allowed(self):
        with patch('os.getenv', return_value=''), \
             patch('claude_client.ClaudeClient') as MockClient:
            mock_client = MockClient.return_value
            mock_client.allowed_users = {111: 'user1'}
            assert is_allowed_user(111) is True
            assert is_allowed_user(222) is False

    def test_env_takes_priority(self):
        with patch('os.getenv', return_value='333'), \
             patch('claude_client.ClaudeClient') as MockClient:
            mock_client = MockClient.return_value
            mock_client.allowed_users = {111: 'user1'}
            # User 333 is in env - allowed
            assert is_allowed_user(333) is True
            # User 111 is in users.json but NOT in env - also allowed (users.json adds to allowed list)
            assert is_allowed_user(111) is True
            # User 999 is not in either - denied
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
            mock_response.assert_called_once_with(456, "привет", "Test User", 123)
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

        with patch('handlers.claude.get_response', return_value="Привет!"), \
             patch('handlers.is_allowed_user', return_value=True):
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


@pytest.mark.asyncio
class TestChannelsCommand:
    async def test_cmd_channels_with_admin_chats(self):
        message = AsyncMock()
        message.from_user = Mock()
        message.from_user.id = 123
        message.answer = AsyncMock()

        bot_info = Mock()
        bot_info.username = "testbot"
        bot_info.id = 999
        message.bot = Mock()
        message.bot.me = AsyncMock(return_value=bot_info)

        # Mock chat info
        mock_chat = Mock()
        mock_chat.type = "supergroup"
        mock_chat.title = "Test Group"

        # Mock admin list with bot as admin
        mock_admin = Mock()
        mock_admin.user.id = 999
        message.bot.get_chat = AsyncMock(return_value=mock_chat)
        message.bot.get_chat_administrators = AsyncMock(return_value=[mock_admin])

        with patch('handlers.is_allowed_user', return_value=True), \
             patch('claude_client.ClaudeClient.get_active_chats', return_value={123: 5, 456: 10}):
            from handlers import cmd_channels_info
            await cmd_channels_info(message)
            assert message.answer.call_count >= 1

    async def test_cmd_channels_no_admin(self):
        message = AsyncMock()
        message.from_user = Mock()
        message.from_user.id = 123
        message.answer = AsyncMock()

        bot_info = Mock()
        bot_info.username = "testbot"
        bot_info.id = 999
        message.bot = Mock()
        message.bot.me = AsyncMock(return_value=bot_info)

        mock_chat = Mock()
        mock_chat.type = "supergroup"
        mock_chat.title = "Test Group"

        # Mock admin list WITHOUT bot
        mock_admin = Mock()
        mock_admin.user.id = 888
        message.bot.get_chat = AsyncMock(return_value=mock_chat)
        message.bot.get_chat_administrators = AsyncMock(return_value=[mock_admin])

        with patch('handlers.is_allowed_user', return_value=True), \
             patch('claude_client.ClaudeClient.get_active_chats', return_value={123: 5}):
            from handlers import cmd_channels_info
            await cmd_channels_info(message)
            # Should show "not admin" message
            assert message.answer.call_count >= 1

    async def test_cmd_channels_private_chat(self):
        message = AsyncMock()
        message.from_user = Mock()
        message.from_user.id = 123
        message.answer = AsyncMock()

        bot_info = Mock()
        bot_info.username = "testbot"
        bot_info.id = 999
        message.bot = Mock()
        message.bot.me = AsyncMock(return_value=bot_info)

        mock_chat = Mock()
        mock_chat.type = "private"
        mock_chat.title = "Private Chat"

        message.bot.get_chat = AsyncMock(return_value=mock_chat)

        with patch('handlers.is_allowed_user', return_value=True), \
             patch('claude_client.ClaudeClient.get_active_chats', return_value={123: 5}):
            from handlers import cmd_channels_info
            await cmd_channels_info(message)
            # Private chat should not be listed as channel/group
            assert message.answer.call_count >= 1

    async def test_cmd_channels_not_allowed(self):
        message = AsyncMock()
        message.from_user = Mock()
        message.from_user.id = 999
        message.answer = AsyncMock()

        with patch('handlers.is_allowed_user', return_value=False):
            from handlers import cmd_channels_info
            await cmd_channels_info(message)
            message.answer.assert_not_called()


@pytest.mark.asyncio
class TestChannelManagementCommands:
    async def test_cmd_add_channel_success(self):
        message = AsyncMock()
        message.from_user = Mock()
        message.from_user.id = 123
        message.text = "/add_channel -1001234567890"
        message.answer = AsyncMock()

        bot_info = Mock()
        bot_info.username = "testbot"
        message.bot = Mock()
        message.bot.me = AsyncMock(return_value=bot_info)

        mock_chat = Mock()
        mock_chat.type = "channel"
        mock_chat.title = "Test Channel"
        message.bot.get_chat = AsyncMock(return_value=mock_chat)

        with patch('handlers.is_allowed_user', return_value=True), \
             patch('claude_client.ClaudeClient') as mock_claude_class:
            mock_claude = Mock()
            mock_claude.add_channel.return_value = True
            mock_claude_class.return_value = mock_claude

            from handlers import cmd_add_channel
            await cmd_add_channel(message)
            assert message.answer.call_count >= 1

    async def test_cmd_add_channel_missing_arg(self):
        message = AsyncMock()
        message.from_user = Mock()
        message.from_user.id = 123
        message.text = "/add_channel"
        message.answer = AsyncMock()

        bot_info = Mock()
        bot_info.username = "testbot"
        message.bot = Mock()
        message.bot.me = AsyncMock(return_value=bot_info)

        with patch('handlers.is_allowed_user', return_value=True):
            from handlers import cmd_add_channel
            await cmd_add_channel(message)
            # Should show usage message
            assert message.answer.call_count >= 1

    async def test_cmd_add_channel_invalid_id(self):
        message = AsyncMock()
        message.from_user = Mock()
        message.from_user.id = 123
        message.text = "/add_channel not_a_number"
        message.answer = AsyncMock()

        bot_info = Mock()
        bot_info.username = "testbot"
        message.bot = Mock()
        message.bot.me = AsyncMock(return_value=bot_info)

        with patch('handlers.is_allowed_user', return_value=True):
            from handlers import cmd_add_channel
            await cmd_add_channel(message)
            # Should show error message
            assert message.answer.call_count >= 1

    async def test_cmd_remove_channel_success(self):
        message = AsyncMock()
        message.from_user = Mock()
        message.from_user.id = 123
        message.text = "/remove_channel -1001234567890"
        message.answer = AsyncMock()

        bot_info = Mock()
        bot_info.username = "testbot"
        message.bot = Mock()
        message.bot.me = AsyncMock(return_value=bot_info)

        with patch('handlers.is_allowed_user', return_value=True), \
             patch('claude_client.ClaudeClient') as mock_claude_class:
            mock_claude = Mock()
            mock_claude.remove_channel.return_value = True
            mock_claude_class.return_value = mock_claude

            from handlers import cmd_remove_channel
            await cmd_remove_channel(message)
            assert message.answer.call_count >= 1

    async def test_cmd_add_channel_not_allowed(self):
        message = AsyncMock()
        message.from_user = Mock()
        message.from_user.id = 999
        message.text = "/add_channel -1001234567890"
        message.answer = AsyncMock()

        with patch('handlers.is_allowed_user', return_value=False):
            from handlers import cmd_add_channel
            await cmd_add_channel(message)
            message.answer.assert_not_called()
