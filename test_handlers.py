import pytest
from unittest.mock import AsyncMock, Mock, patch
from aiogram.types import Message
from mentions import is_mention
from permissions import is_allowed_user
from handlers import handle_message
from commands import (
    cmd_start,
    cmd_clear,
    cmd_help,
    cmd_chats,
    cmd_channels_info,
    cmd_add_channel,
    cmd_remove_channel,
    cmd_user_add,
    cmd_user_del,
    cmd_users_list,
)


@pytest.fixture
def mock_claude():
    client = Mock()
    client.get_response = AsyncMock(return_value="Привет!")
    client.clear_history = Mock()
    client.add_channel = Mock(return_value=True)
    client.remove_channel = Mock(return_value=True)
    client.get_active_chats = Mock(return_value={})
    client.get_monitored_channels = Mock(return_value=set())
    client.add_user = Mock(return_value=True)
    client.remove_user = Mock(return_value=True)
    client.get_allowed_users = Mock(return_value={})
    return client


@pytest.fixture
def message_factory(mock_claude):
    def _make(
        user_id=123,
        full_name="Test User",
        chat_id=456,
        chat_type='private',
        text="привет",
    ):
        msg = AsyncMock(spec=Message)
        msg.from_user = Mock()
        msg.from_user.id = user_id
        msg.from_user.full_name = full_name
        msg.chat = Mock()
        msg.chat.id = chat_id
        msg.chat.type = chat_type
        msg.text = text
        msg.answer = AsyncMock()
        msg.chat.send_action = AsyncMock()

        bot_info = Mock()
        bot_info.username = "testbot"
        msg.bot = Mock()
        msg.bot.me = AsyncMock(return_value=bot_info)
        return msg
    return _make


# --- is_allowed_user tests ---

class TestIsAllowedUser:
    def test_no_allowed_users_env(self):
        with patch('os.getenv', return_value=''), \
             patch('permissions.ClaudeClient') as MockClient:
            mock_client = MockClient.return_value
            mock_client.allowed_users = {}
            assert is_allowed_user(123) is False
            assert is_allowed_user(456) is False

    def test_with_allowed_users(self):
        with patch('os.getenv', return_value='123,456,789'), \
             patch('permissions.ClaudeClient') as MockClient:
            mock_client = MockClient.return_value
            mock_client.allowed_users = {}
            assert is_allowed_user(123) is True
            assert is_allowed_user(456) is True
            assert is_allowed_user(999) is False

    def test_users_json_allowed(self):
        with patch('os.getenv', return_value=''), \
             patch('permissions.ClaudeClient') as MockClient:
            mock_client = MockClient.return_value
            mock_client.allowed_users = {111: 'user1'}
            assert is_allowed_user(111) is True
            assert is_allowed_user(222) is False

    def test_env_takes_priority(self):
        with patch('os.getenv', return_value='333'), \
             patch('permissions.ClaudeClient') as MockClient:
            mock_client = MockClient.return_value
            mock_client.allowed_users = {111: 'user1'}
            assert is_allowed_user(333) is True
            assert is_allowed_user(111) is True
            assert is_allowed_user(999) is False


# --- is_mention tests ---

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


# --- handle_message tests ---

@pytest.mark.asyncio
class TestHandleMessage:
    async def test_private_chat_allowed_user(self, message_factory, mock_claude):
        message = message_factory(user_id=123, chat_id=456)
        with patch('handlers.is_allowed_user', return_value=True), \
             patch.object(mock_claude, 'get_response', return_value="Привет!"):
            await handle_message(message, claude=mock_claude)
            mock_claude.get_response.assert_called_once_with(456, "привет", "Test User", 123)
            message.answer.assert_called_once()

    async def test_private_chat_not_allowed(self, message_factory, mock_claude):
        message = message_factory(user_id=999)
        with patch('handlers.is_allowed_user', return_value=False):
            await handle_message(message, claude=mock_claude)
            message.answer.assert_not_called()

    async def test_group_with_mention(self, message_factory, mock_claude):
        message = message_factory(user_id=999, chat_id=789, chat_type='group', text="@testbot привет")
        with patch('mentions.is_mention', return_value=True), \
             patch('handlers.is_allowed_user', return_value=True), \
             patch.object(mock_claude, 'get_response', return_value="Привет!"):
            await handle_message(message, claude=mock_claude)
            message.answer.assert_called_once()

    async def test_group_without_mention(self, message_factory, mock_claude):
        message = message_factory(user_id=123, chat_id=789, chat_type='group', text="просто текст")
        with patch('mentions.is_mention', return_value=False):
            await handle_message(message, claude=mock_claude)
            message.answer.assert_not_called()

    async def test_long_response_splitting(self, message_factory, mock_claude):
        message = message_factory(user_id=123, chat_id=456, text="расскажи много")
        long_response = "x" * 5000
        with patch('handlers.is_allowed_user', return_value=True), \
             patch.object(mock_claude, 'get_response', return_value=long_response):
            await handle_message(message, claude=mock_claude)
            assert message.answer.call_count == 2

    async def test_empty_text_after_mention_removal(self, message_factory, mock_claude):
        message = message_factory(user_id=123, text="@testbot")
        bot_info = Mock()
        bot_info.username = "testbot"
        message.bot.me = AsyncMock(return_value=bot_info)
        with patch('handlers.is_allowed_user', return_value=True), \
             patch('mentions.is_mention', return_value=True):
            await handle_message(message, claude=mock_claude)
            message.answer.assert_called_once_with("Да? Чем могу помочь?")


# --- Command handler tests ---

@pytest.mark.asyncio
class TestCmdStart:
    async def test_allowed(self, message_factory, mock_claude):
        message = message_factory(user_id=123)
        with patch('commands.is_allowed_user', return_value=True):
            await cmd_start(message)
            message.answer.assert_called_once()
            assert "SkyNet" in message.answer.call_args[0][0]

    async def test_not_allowed(self, message_factory, mock_claude):
        message = message_factory(user_id=999)
        with patch('commands.is_allowed_user', return_value=False):
            await cmd_start(message)
            message.answer.assert_called_once_with("У вас нет доступа к этому боту")


@pytest.mark.asyncio
class TestCmdClear:
    async def test_clear(self, message_factory, mock_claude):
        message = message_factory(user_id=123, chat_id=456)
        with patch('commands.is_allowed_user', return_value=True):
            await cmd_clear(message, claude=mock_claude)
            mock_claude.clear_history.assert_called_once_with(456)
            message.answer.assert_called_once_with("История диалога очищена")

    async def test_not_allowed(self, message_factory, mock_claude):
        message = message_factory(user_id=999)
        with patch('commands.is_allowed_user', return_value=False):
            await cmd_clear(message, claude=mock_claude)
            message.answer.assert_not_called()


@pytest.mark.asyncio
class TestCmdHelp:
    async def test_help(self, message_factory, mock_claude):
        message = message_factory(user_id=123)
        with patch('commands.is_allowed_user', return_value=True):
            await cmd_help(message, claude=mock_claude)
            message.answer.assert_called_once()

    async def test_not_allowed(self, message_factory, mock_claude):
        message = message_factory(user_id=999)
        with patch('commands.is_allowed_user', return_value=False):
            await cmd_help(message, claude=mock_claude)
            message.answer.assert_not_called()


@pytest.mark.asyncio
class TestCmdChats:
    async def test_with_chats(self, message_factory, mock_claude):
        message = message_factory(user_id=123)
        mock_claude.get_active_chats.return_value = {123: 5, 456: 10}
        with patch('commands.is_allowed_user', return_value=True):
            await cmd_chats(message, claude=mock_claude)
            message.answer.assert_called_once()

    async def test_empty(self, message_factory, mock_claude):
        message = message_factory(user_id=123)
        mock_claude.get_active_chats.return_value = {}
        with patch('commands.is_allowed_user', return_value=True):
            await cmd_chats(message, claude=mock_claude)
            message.answer.assert_called_once_with("Нет активных чатов с историей")


@pytest.mark.asyncio
class TestCmdChannelsInfo:
    async def test_empty(self, message_factory, mock_claude):
        message = message_factory(user_id=123)
        mock_claude.get_monitored_channels.return_value = set()
        mock_claude.get_active_chats.return_value = {}
        with patch('commands.is_allowed_user', return_value=True):
            await cmd_channels_info(message, claude=mock_claude)
            assert message.answer.call_count >= 1

    async def test_not_allowed(self, message_factory, mock_claude):
        message = message_factory(user_id=999)
        with patch('commands.is_allowed_user', return_value=False):
            await cmd_channels_info(message, claude=mock_claude)
            message.answer.assert_not_called()


@pytest.mark.asyncio
class TestCmdAddChannel:
    async def test_success(self, message_factory, mock_claude):
        message = message_factory(user_id=123, text="/add_channel -1001234567890")
        mock_chat = Mock()
        mock_chat.type = "channel"
        mock_chat.title = "Test Channel"
        message.bot.get_chat = AsyncMock(return_value=mock_chat)
        mock_claude.add_channel.return_value = True
        with patch('commands.is_allowed_user', return_value=True):
            await cmd_add_channel(message, claude=mock_claude)
            assert message.answer.call_count >= 1

    async def test_missing_arg(self, message_factory, mock_claude):
        message = message_factory(user_id=123, text="/add_channel")
        with patch('commands.is_allowed_user', return_value=True):
            await cmd_add_channel(message, claude=mock_claude)
            assert message.answer.call_count >= 1

    async def test_invalid_id(self, message_factory, mock_claude):
        message = message_factory(user_id=123, text="/add_channel not_a_number")
        with patch('commands.is_allowed_user', return_value=True):
            await cmd_add_channel(message, claude=mock_claude)
            assert message.answer.call_count >= 1

    async def test_not_allowed(self, message_factory, mock_claude):
        message = message_factory(user_id=999, text="/add_channel -1001234567890")
        with patch('commands.is_allowed_user', return_value=False):
            await cmd_add_channel(message, claude=mock_claude)
            message.answer.assert_not_called()


@pytest.mark.asyncio
class TestCmdRemoveChannel:
    async def test_success(self, message_factory, mock_claude):
        message = message_factory(user_id=123, text="/remove_channel -1001234567890")
        mock_claude.remove_channel.return_value = True
        with patch('commands.is_allowed_user', return_value=True):
            await cmd_remove_channel(message, claude=mock_claude)
            assert message.answer.call_count >= 1


@pytest.mark.asyncio
class TestCmdUserAdd:
    async def test_success(self, message_factory, mock_claude):
        message = message_factory(user_id=123, text="/user_add 999888777")
        mock_chat = Mock()
        mock_chat.username = "newuser"
        message.bot.get_chat = AsyncMock(return_value=mock_chat)
        mock_claude.add_user.return_value = True
        with patch('commands.is_allowed_user', return_value=True):
            await cmd_user_add(message, claude=mock_claude)
            assert message.answer.call_count >= 1

    async def test_not_private(self, message_factory, mock_claude):
        message = message_factory(user_id=123, text="/user_add 999", chat_type='group')
        await cmd_user_add(message, claude=mock_claude)
        assert "личн" in message.answer.call_args[0][0].lower()


@pytest.mark.asyncio
class TestCmdUserDel:
    async def test_success(self, message_factory, mock_claude):
        message = message_factory(user_id=123, text="/user_del 999888777")
        mock_claude.remove_user.return_value = True
        with patch('commands.is_allowed_user', return_value=True):
            await cmd_user_del(message, claude=mock_claude)
            assert message.answer.call_count >= 1


@pytest.mark.asyncio
class TestCmdUsersList:
    async def test_list(self, message_factory, mock_claude):
        message = message_factory(user_id=123)
        mock_claude.get_allowed_users.return_value = {111: "user1", 222: "user2"}
        with patch('commands.is_allowed_user', return_value=True):
            await cmd_users_list(message, claude=mock_claude)
            message.answer.assert_called_once()
