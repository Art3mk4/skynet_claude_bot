import os
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, List, Set, Tuple
from openai import AsyncOpenAI
import aiofiles

logger = logging.getLogger(__name__)


class ClaudeClient:
    def __init__(self):
        api_key = os.getenv('OMNIROUTE_API_KEY')
        if not api_key:
            raise ValueError("OMNIROUTE_API_KEY not found in environment")
        base_url = os.getenv('OMNIROUTE_BASE_URL', 'http://localhost:20128/v1')
        self.model = os.getenv('OMNIROUTE_MODEL', 'kr/claude-sonnet-4.5')

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=60.0
        )
        self.conversations: Dict[int, List[dict]] = {}
        self.monitored_channels: Set[int] = set()
        # users.json: {"users": [{"id": 123, "username": "user1"}]}
        self.allowed_users: Dict[int, str] = {}
        self.conversations_dir = Path("conversations")
        self.channels_file = self.conversations_dir / "channels.json"
        self.users_file = self.conversations_dir / "users.json"
        self.conversations_dir.mkdir(exist_ok=True)

        # Async locks для защиты от race conditions при записи
        self._conversation_locks: Dict[int, asyncio.Lock] = {}
        self._channels_lock = asyncio.Lock()
        self._users_lock = asyncio.Lock()

        # Clear users.json in test mode (pytest runs)
        if os.getenv('TEST_MODE') == '1' and self.users_file.exists():
            self.users_file.unlink()

        # Загружаем сохраненные диалоги, каналы и пользователей
        self._load_conversations()
        self._load_monitored_channels()
        self._load_allowed_users()

    def _get_conversation_file(self, chat_id: int) -> Path:
        return self.conversations_dir / f"chat_{chat_id}.json"

    def _load_conversations(self):
        """Загружает сохраненные диалоги"""
        for file in self.conversations_dir.glob("chat_*.json"):
            try:
                chat_id = int(file.stem.split('_')[1])
                with open(file, 'r', encoding='utf-8') as f:
                    self.conversations[chat_id] = json.load(f)
                logger.info(f"Loaded conversation for chat {chat_id}")
            except Exception as e:
                logger.error(f"Error loading conversation from {file}: {e}")

    async def _save_conversation(self, chat_id: int):
        """Сохраняет диалог на диск с защитой от race conditions"""
        if chat_id not in self._conversation_locks:
            self._conversation_locks[chat_id] = asyncio.Lock()

        async with self._conversation_locks[chat_id]:
            try:
                file = self._get_conversation_file(chat_id)
                async with aiofiles.open(file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(self.conversations[chat_id], ensure_ascii=False, indent=2))
            except Exception as e:
                logger.error(f"Error saving conversation for chat {chat_id}: {e}")

    def clear_history(self, chat_id: int):
        """Очищает историю диалога"""
        if chat_id in self.conversations:
            del self.conversations[chat_id]

        file = self._get_conversation_file(chat_id)
        if file.exists():
            file.unlink()

        # Cleanup lock to prevent memory leak
        if chat_id in self._conversation_locks:
            del self._conversation_locks[chat_id]

        logger.info(f"Cleared conversation for chat {chat_id}")

    def _load_monitored_channels(self):
        """Загружает список мониторируемых каналов"""
        if self.channels_file.exists():
            try:
                with open(self.channels_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.monitored_channels = set(data.get('channels', []))
                logger.info(f"Loaded {len(self.monitored_channels)} monitored channels")
            except Exception as e:
                logger.error(f"Error loading channels file: {e}")

    async def _save_monitored_channels(self):
        """Сохраняет список мониторируемых каналов с защитой от race conditions"""
        async with self._channels_lock:
            try:
                async with aiofiles.open(self.channels_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps({'channels': list(self.monitored_channels)}, ensure_ascii=False, indent=2))
            except Exception as e:
                logger.error(f"Error saving channels file: {e}")

    async def add_channel(self, chat_id: int) -> bool:
        """Добавляет канал в список мониторинга"""
        if chat_id in self.monitored_channels:
            return False
        self.monitored_channels.add(chat_id)
        await self._save_monitored_channels()
        logger.info(f"Added channel {chat_id} to monitored channels")
        return True

    async def remove_channel(self, chat_id: int) -> bool:
        """Удаляет канал из списка мониторинга"""
        if chat_id not in self.monitored_channels:
            return False
        self.monitored_channels.discard(chat_id)
        await self._save_monitored_channels()
        logger.info(f"Removed channel {chat_id} from monitored channels")
        return True

    def get_monitored_channels(self) -> Set[int]:
        """Возвращает список мониторируемых каналов"""
        return self.monitored_channels.copy()

    def _load_allowed_users(self):
        """Загружает список разрешенных пользователей из users.json"""
        if self.users_file.exists():
            try:
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    users_list = data.get('users', [])
                    # Support both old format [123, 456] and new format [{id: 123, username: "user"}]
                    if users_list and isinstance(users_list[0], int):
                        # Old format: [123, 456]
                        self.allowed_users = {uid: "" for uid in users_list}
                    else:
                        # New format: [{"id": 123, "username": "user1"}]
                        self.allowed_users = {u['id']: u.get('username', '') for u in users_list}
                logger.info(f"Loaded {len(self.allowed_users)} allowed users")
            except Exception as e:
                logger.error(f"Error loading users file: {e}")

    async def _save_allowed_users(self):
        """Сохраняет список разрешенных пользователей с защитой от race conditions"""
        async with self._users_lock:
            try:
                async with aiofiles.open(self.users_file, 'w', encoding='utf-8') as f:
                    # Convert dict to list of dicts
                    users_list = [{"id": uid, "username": uname} for uid, uname in self.allowed_users.items()]
                    await f.write(json.dumps({'users': users_list}, ensure_ascii=False, indent=2))
            except Exception as e:
                logger.error(f"Error saving users file: {e}")

    async def add_user(self, user_id: int, username: str = "") -> bool:
        """Добавляет пользователя в список разрешенных"""
        if user_id in self.allowed_users:
            return False
        self.allowed_users[user_id] = username
        await self._save_allowed_users()
        logger.info(f"Added user {user_id} ({username}) to allowed users")
        return True

    async def remove_user(self, user_id: int) -> bool:
        """Удаляет пользователя из списка разрешенных"""
        if user_id not in self.allowed_users:
            return False
        del self.allowed_users[user_id]
        await self._save_allowed_users()
        logger.info(f"Removed user {user_id} from allowed users")
        return True

    def is_user_allowed(self, user_id: int) -> bool:
        """Проверяет, разрешен ли пользователь (из users.json)"""
        return user_id in self.allowed_users

    def get_allowed_users(self) -> Dict[int, str]:
        """Возвращает словарь разрешенных пользователей {id: username}"""
        return self.allowed_users.copy()

    def get_active_chats(self) -> Dict[int, int]:
        """Возвращает словарь активных чатов и количество сообщений в них"""
        result = {chat_id: len(messages) for chat_id, messages in self.conversations.items()}
        # Добавляем каналы из мониторинга (даже без истории)
        for channel_id in self.monitored_channels:
            if channel_id not in result:
                result[channel_id] = 0
        return result

    async def get_response(self, chat_id: int, user_message: str, user_name: str = "User", user_id: int = None) -> str:
        """Получает ответ от Claude через OmniRoute"""

        # Инициализируем историю если нужно
        if chat_id not in self.conversations:
            self.conversations[chat_id] = []

        # Добавляем сообщение пользователя с метаданными
        self.conversations[chat_id].append({
            "role": "user",
            "content": user_message,
            "user_id": user_id,
            "user_name": user_name
        })

        # Ограничиваем историю последними 20 сообщениями
        if len(self.conversations[chat_id]) > 20:
            self.conversations[chat_id] = self.conversations[chat_id][-20:]

        try:
            # Отправляем запрос к OmniRoute (OpenAI-compatible API)
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": f"Ты SkyNet, AI ассистент на базе Claude от Anthropic. Ты общаешься с пользователем {user_name} в Telegram чате. Отвечай на русском языке, будь дружелюбным и полезным. Используй Markdown для форматирования когда нужно. Ты - умный помощник, который всегда готов помочь с любыми вопросами."
                    },
                    *self.conversations[chat_id]
                ],
                max_tokens=4096,
                temperature=0.7
            )

            # Извлекаем текст ответа
            assistant_message = response.choices[0].message.content

            # Добавляем ответ в историю
            self.conversations[chat_id].append({
                "role": "assistant",
                "content": assistant_message,
                "user_id": None,
                "user_name": "SkyNet"
            })

            # Сохраняем диалог (не критично, если упадёт)
            try:
                await self._save_conversation(chat_id)
            except Exception as save_error:
                logger.error(f"Failed to save conversation for chat {chat_id}: {save_error}")

            return assistant_message

        except Exception as e:
            logger.error(f"Error calling OmniRoute API: {e}")
            # Убираем последнее сообщение пользователя при ошибке
            if self.conversations[chat_id]:
                self.conversations[chat_id].pop()
            raise
