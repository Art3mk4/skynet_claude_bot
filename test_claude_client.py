import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, mock_open
from claude_client import ClaudeClient


@pytest.fixture
def temp_conversations_dir(tmp_path):
    conversations_dir = tmp_path / "conversations"
    conversations_dir.mkdir()
    return conversations_dir


@pytest.fixture
def claude_client(temp_conversations_dir):
    with patch.object(Path, 'mkdir'), \
         patch('claude_client.Path', return_value=temp_conversations_dir):
        with patch.dict('os.environ', {
            'OMNIROUTE_API_KEY': 'test_key',
            'OMNIROUTE_BASE_URL': 'http://test.local/v1',
            'OMNIROUTE_MODEL': 'test-model'
        }):
            client = ClaudeClient()
            client.conversations_dir = temp_conversations_dir
            return client


class TestClaudeClientInit:
    def test_init_with_env_vars(self):
        with patch.dict('os.environ', {
            'OMNIROUTE_API_KEY': 'my_key',
            'OMNIROUTE_BASE_URL': 'http://custom.url/v1',
            'OMNIROUTE_MODEL': 'custom-model'
        }), patch.object(Path, 'mkdir'), patch('claude_client.ClaudeClient._load_conversations'):
            client = ClaudeClient()
            assert client.model == 'custom-model'

    def test_init_with_defaults(self):
        with patch.dict('os.environ', {}, clear=True), \
             patch.object(Path, 'mkdir'), \
             patch('claude_client.ClaudeClient._load_conversations'):
            client = ClaudeClient()
            assert client.model == 'kr/claude-sonnet-4.5'


class TestConversationManagement:
    def test_get_conversation_file(self, claude_client):
        file_path = claude_client._get_conversation_file(123)
        assert file_path.name == "chat_123.json"

    def test_save_conversation(self, claude_client, temp_conversations_dir):
        chat_id = 123
        claude_client.conversations[chat_id] = [
            {"role": "user", "content": "test"},
            {"role": "assistant", "content": "response"}
        ]

        claude_client._save_conversation(chat_id)

        file_path = temp_conversations_dir / "chat_123.json"
        assert file_path.exists()

        with open(file_path, 'r') as f:
            data = json.load(f)
        assert len(data) == 2
        assert data[0]["role"] == "user"

    def test_load_conversations(self, temp_conversations_dir):
        # Создаем тестовый файл
        test_data = [{"role": "user", "content": "hello"}]
        file_path = temp_conversations_dir / "chat_456.json"
        with open(file_path, 'w') as f:
            json.dump(test_data, f)

        with patch.dict('os.environ', {
            'OMNIROUTE_API_KEY': 'test_key'
        }), patch.object(Path, 'mkdir'):
            client = ClaudeClient()
            client.conversations_dir = temp_conversations_dir
            client._load_conversations()

            assert 456 in client.conversations
            assert client.conversations[456] == test_data

    def test_clear_history(self, claude_client, temp_conversations_dir):
        chat_id = 789
        claude_client.conversations[chat_id] = [{"role": "user", "content": "test"}]

        file_path = temp_conversations_dir / "chat_789.json"
        file_path.write_text('[]')

        claude_client.clear_history(chat_id)

        assert chat_id not in claude_client.conversations
        assert not file_path.exists()


@pytest.mark.asyncio
class TestGetResponse:
    async def test_get_response_new_conversation(self, claude_client):
        chat_id = 100
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Test response"

        claude_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(claude_client, '_save_conversation'):
            response = await claude_client.get_response(chat_id, "Hello", "TestUser")

        assert response == "Test response"
        assert chat_id in claude_client.conversations
        assert len(claude_client.conversations[chat_id]) == 2
        assert claude_client.conversations[chat_id][0]["role"] == "user"
        assert claude_client.conversations[chat_id][1]["role"] == "assistant"

    async def test_get_response_existing_conversation(self, claude_client):
        chat_id = 200
        claude_client.conversations[chat_id] = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "First response"}
        ]

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Second response"

        claude_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(claude_client, '_save_conversation'):
            response = await claude_client.get_response(chat_id, "Second message", "TestUser")

        assert response == "Second response"
        assert len(claude_client.conversations[chat_id]) == 4

    async def test_get_response_history_limit(self, claude_client):
        chat_id = 300
        # Создаем историю из 25 сообщений
        claude_client.conversations[chat_id] = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
            for i in range(25)
        ]

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Response"

        claude_client.client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(claude_client, '_save_conversation'):
            await claude_client.get_response(chat_id, "New message", "TestUser")

        # История должна быть ограничена 20 сообщениями + новое сообщение + ответ
        assert len(claude_client.conversations[chat_id]) <= 22

    async def test_get_response_api_error(self, claude_client):
        chat_id = 400

        claude_client.client.chat.completions.create = AsyncMock(
            side_effect=Exception("API Error")
        )

        with pytest.raises(Exception, match="API Error"):
            await claude_client.get_response(chat_id, "Test", "TestUser")

        # Сообщение пользователя должно быть удалено при ошибке
        assert chat_id not in claude_client.conversations or \
               len(claude_client.conversations[chat_id]) == 0

    async def test_get_response_calls_api_correctly(self, claude_client):
        chat_id = 500

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Response"

        mock_create = AsyncMock(return_value=mock_response)
        claude_client.client.chat.completions.create = mock_create

        with patch.object(claude_client, '_save_conversation'):
            await claude_client.get_response(chat_id, "Test message", "John")

        mock_create.assert_called_once()
        call_args = mock_create.call_args[1]

        assert call_args['model'] == claude_client.model
        assert call_args['max_tokens'] == 4096
        assert call_args['temperature'] == 0.7
        assert len(call_args['messages']) == 2  # system + user message
        assert call_args['messages'][0]['role'] == 'system'
        assert 'John' in call_args['messages'][0]['content']
