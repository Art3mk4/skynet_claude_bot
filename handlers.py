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


async def is_mention(message: Message) -> bool:
    """Проверяет упоминание бота в сообщении"""
    if not message.text:
        return False

    bot_info = await message.bot.me()
    bot_username = bot_info.username
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
        "Работаю в группах, каналах и комментариях к постам.\n\n"
        "Команды:\n"
        "/start - Начать\n"
        "/clear - Очистить историю диалога\n"
        "/chats - Список активных чатов\n"
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
        "Работаю в личных чатах, группах, каналах и комментариях.\n"
        "Я запоминаю контекст разговора в рамках чата.\n\n"
        "Команды:\n"
        "/clear - Очистить историю\n"
        "/chats - Список активных чатов\n"
        "/help - Эта справка"
    )


@router.message(Command('chats'))
async def cmd_chats(message: Message):
    if not is_allowed_user(message.from_user.id):
        return

    from claude_client import ClaudeClient
    active_chats = claude.get_active_chats()

    if not active_chats:
        await message.answer("Нет активных чатов с историей")
        return

    response = "📊 Активные чаты:\n\n"
    for chat_id, msg_count in active_chats.items():
        chat_type = "Личный чат" if chat_id > 0 else "Группа"
        response += f"• Chat ID: `{chat_id}` ({chat_type})\n  Сообщений в истории: {msg_count}\n\n"

    await message.answer(response)


@router.message(F.text)
async def handle_message(message: Message):
    logger.info(f"📩 Message received: user={message.from_user.id}, chat={message.chat.id}, type={message.chat.type}, text='{message.text[:50]}'")

    # В личке проверяем ALLOWED_USERS
    is_private = message.chat.type == 'private'

    if is_private and not is_allowed_user(message.from_user.id):
        logger.info(f"⏭️ User {message.from_user.id} not in ALLOWED_USERS, ignoring private chat")
        return

    logger.info(f"Chat type: {message.chat.type}, is_private: {is_private}")

    # В группах/каналах отвечаем только при упоминании
    if not is_private and not await is_mention(message):
        logger.info("Not a mention in group/channel/comments, ignoring")
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
        logger.info(f"✅ Got response from Claude, length: {len(response)}")

        # Разбиваем длинные сообщения
        if len(response) > 4096:
            logger.info(f"Splitting long message into chunks")
            for i in range(0, len(response), 4096):
                await message.answer(response[i:i+4096])
                logger.info(f"Sent chunk {i//4096 + 1}")
        else:
            await message.answer(response)
            logger.info(f"✅ Message sent successfully")

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        await message.answer(f"Произошла ошибка: {str(e)}")
