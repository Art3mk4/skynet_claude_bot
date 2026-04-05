import os
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from claude_client import ClaudeClient

router = Router()
logger = logging.getLogger(__name__)

claude = ClaudeClient()


def is_allowed_user(user_id: int) -> bool:
    allowed = os.getenv('ALLOWED_USERS', '')
    if not allowed:
        return True
    return str(user_id) in allowed.split(',')


def is_mention(message: Message) -> bool:
    """Проверяет упоминание бота в сообщении"""
    if not message.text:
        return False

    bot_username = message.bot.username
    text_lower = message.text.lower()

    # Проверка @username или просто имени
    return (f'@{bot_username}'.lower() in text_lower or
            'skynet' in text_lower or
            'скайнет' in text_lower)


@router.message(CommandStart())
async def cmd_start(message: Message):
    if not is_allowed_user(message.from_user.id):
        await message.answer("У вас нет доступа к этому боту")
        return

    await message.answer(
        "Привет! Я SkyNet, AI ассистент на базе Claude от Anthropic.\n\n"
        "Упомяни меня (@username или просто 'skynet') в сообщении, и я отвечу.\n"
        "Команды:\n"
        "/start - Начать\n"
        "/clear - Очистить историю диалога\n"
        "/help - Помощь"
    )


@router.message(Command('clear'))
async def cmd_clear(message: Message):
    if not is_allowed_user(message.from_user.id):
        return

    chat_id = message.chat.id
    claude.clear_history(chat_id)
    await message.answer("История диалога очищена")


@router.message(Command('help'))
async def cmd_help(message: Message):
    if not is_allowed_user(message.from_user.id):
        return

    await message.answer(
        "Я SkyNet, AI ассистент на базе Claude.\n\n"
        "Упомяни меня в сообщении:\n"
        "• @bot_username что такое Python?\n"
        "• skynet, помоги с кодом\n\n"
        "Я запоминаю контекст разговора в рамках чата.\n\n"
        "Команды:\n"
        "/clear - Очистить историю\n"
        "/help - Эта справка"
    )


@router.message(F.text)
async def handle_message(message: Message):
    logger.info(f"Received message from user {message.from_user.id} in chat {message.chat.id} (type: {message.chat.type}): {message.text[:50]}")

    if not is_allowed_user(message.from_user.id):
        logger.warning(f"User {message.from_user.id} not allowed")
        return

    # В личке отвечаем всегда, в группах только при упоминании
    is_private = message.chat.type == 'private'
    logger.info(f"Is private chat: {is_private}")

    if not is_private and not is_mention(message):
        logger.info("Not a mention in group chat, ignoring")
        return

    # Убираем упоминание из текста
    text = message.text
    bot_info = await message.bot.me()
    bot_username = bot_info.username
    text = text.replace(f'@{bot_username}', '').replace('skynet', '').replace('скайнет', '').strip()

    if not text:
        await message.answer("Да? Чем могу помочь?")
        return

    # Показываем что бот печатает
    await message.chat.do("typing")

    try:
        chat_id = message.chat.id
        user_name = message.from_user.full_name or message.from_user.username or "User"

        response = await claude.get_response(chat_id, text, user_name)

        # Разбиваем длинные сообщения
        if len(response) > 4096:
            for i in range(0, len(response), 4096):
                await message.answer(response[i:i+4096])
        else:
            await message.answer(response)

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await message.answer(f"Произошла ошибка: {str(e)}")
