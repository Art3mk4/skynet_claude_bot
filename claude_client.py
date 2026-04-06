import os
import json
import logging
from pathlib import Path
from typing import Dict, List
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class ClaudeClient:
    def __init__(self):
        api_key = os.getenv('OMNIROUTE_API_KEY') or 'dummy'
        base_url = os.getenv('OMNIROUTE_BASE_URL', 'http://localhost:20128/v1')
        self.model = os.getenv('OMNIROUTE_MODEL', 'kr/claude-sonnet-4.5')

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=60.0
        )
        self.conversations: Dict[int, List[dict]] = {}
        self.conversations_dir = Path("conversations")
        self.conversations_dir.mkdir(exist_ok=True)

        # Загружаем сохраненные диалоги
        self._load_conversations()

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

    def _save_conversation(self, chat_id: int):
        """Сохраняет диалог на диск"""
        try:
            file = self._get_conversation_file(chat_id)
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(self.conversations[chat_id], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving conversation for chat {chat_id}: {e}")

    def clear_history(self, chat_id: int):
        """Очищает историю диалога"""
        if chat_id in self.conversations:
            del self.conversations[chat_id]

        file = self._get_conversation_file(chat_id)
        if file.exists():
            file.unlink()

        logger.info(f"Cleared conversation for chat {chat_id}")

    def get_active_chats(self) -> Dict[int, int]:
        """Возвращает словарь активных чатов и количество сообщений в них"""
        return {chat_id: len(messages) for chat_id, messages in self.conversations.items()}

    async def get_response(self, chat_id: int, user_message: str, user_name: str = "User") -> str:
        """Получает ответ от Claude через OmniRoute"""

        # Инициализируем историю если нужно
        if chat_id not in self.conversations:
            self.conversations[chat_id] = []

        # Добавляем сообщение пользователя
        self.conversations[chat_id].append({
            "role": "user",
            "content": user_message
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
                "content": assistant_message
            })

            # Сохраняем диалог
            self._save_conversation(chat_id)

            return assistant_message

        except Exception as e:
            logger.error(f"Error calling OmniRoute API: {e}")
            # Убираем последнее сообщение пользователя при ошибке
            if self.conversations[chat_id]:
                self.conversations[chat_id].pop()
            raise
