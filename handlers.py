import os
import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command, CommandObject
from claude_client import ClaudeClient

router = Router()
logger = logging.getLogger(__name__)

claude = ClaudeClient()


def is_allowed_user(user_id: int) -> bool:
    # Сначала проверяем ALLOWED_USERS env (приоритет)
    allowed = os.getenv('ALLOWED_USERS', '')
    logger.info(f"is_allowed_user({user_id}): ALLOWED_USERS='{allowed}'")
    if allowed:
        # Если env задан, проверяем только его
        result = str(user_id) in allowed.split(',')
        logger.info(f"  -> result={result} (from env)")
        return result

    # Если env не задан, разрешаем всех пользователей (без ограничений)
    logger.info(f"  -> result=True (no restrictions)")
    return True


async def is_mention(message: Message) -> bool:
    """Проверяет упоминание бота в сообщении"""
    if not message.text:
        return False

    bot_info = await message.bot.me()
    bot_username = bot_info.username
    text_lower = message.text.lower()

    # Проверка через entities (наиболее надежный способ)
    # Используем getattr для совместимости с моками в тестах
    if getattr(message, 'entities', None):
        for entity in message.entities:
            if entity.type == "mention":
                # Извлекаем username из текста по позиции
                mentioned_text = message.text[entity.offset:entity.offset + entity.length]
                if mentioned_text.lower() == f'@{bot_username}'.lower():
                    logger.info(f".is_mention: found @ mention via entities: {mentioned_text}")
                    return True

    # Проверка @username в тексте
    is_mention_username = f'@{bot_username}'.lower() in text_lower

    # Также проверяем без @ (вдруг приходит без собачки)
    is_mention_username_no_at = bot_username.lower() in text_lower

    is_mention_name = 'skynet' in text_lower or 'скайнет' in text_lower

    logger.info(f".is_mention check: username='{bot_username}', text='{message.text[:50]}', entities={bool(getattr(message, 'entities', None))}, mention_username={is_mention_username}, mention_no_at={is_mention_username_no_at}, mention_name={is_mention_name}")

    return is_mention_username or is_mention_username_no_at or is_mention_name


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
        "/chats - Список активных чатов с историей\n"
        "/channels - Список каналов и групп, где я администратор\n"
        "/users - Список разрешенных пользователей\n"
        "/user_add <id> - Добавить пользователя\n"
        "/user_del <id> - Удалить пользователя\n"
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
        "/channels - Мониторируемые каналы\n"
        "/users - Список разрешенных пользователей\n"
        "/user_add <id> - Добавить пользователя\n"
        "/user_del <id> - Удалить пользователя\n"
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

    response = "📊 Активные чаты (история):\n\n"
    for chat_id, msg_count in active_chats.items():
        chat_type = "Личный чат" if chat_id > 0 else "Группа"
        response += f"• Chat ID: `{chat_id}` ({chat_type})\n  Сообщений в истории: {msg_count}\n\n"

    response += "Используй /channels для просмотра мониторируемых каналов и каналов, где бот администратор."

    await message.answer(response)


@router.message(Command('channels'))
async def cmd_channels_info(message: Message):
    """Показывает мониторируемые каналы и каналы где бот админ"""
    if not is_allowed_user(message.from_user.id):
        return

    await message.answer("📊 Получение информации о каналах...", parse_mode=None)

    from claude_client import ClaudeClient
    claude = ClaudeClient()

    monitored_channels = claude.get_monitored_channels()
    active_chats = claude.get_active_chats()

    bot_info = await message.bot.me()
    bot_id = bot_info.id

    response = "Мониторируемые каналы:\n\n"

    if not monitored_channels and not active_chats:
        await message.answer(
            "Нет активных чатов и мониторируемых каналов.\n\n"
            "Для добавления канала используй:\n"
            "/add_channel <channel_id>\n\n"
            "Чтобы узнать ID канала:\n"
            "- Перешли сообщение из канала @userinfobot или @getidsbot\n"
            "- Или посмотри в URL: https://web.telegram.org/k/#-<channel_id>",
            parse_mode=None
        )
        return

    # Показываем мониторируемые каналы
    if monitored_channels:
        response += "Добавленные вручную:\n"
        for chat_id in monitored_channels:
            try:
                chat = await message.bot.get_chat(chat_id)
                title = chat.title or "Без названия"
                response += f"- {title}\n  ID: {chat_id}\n  Тип: {chat.type}\n\n"
            except Exception as e:
                logger.warning(f"Cannot get chat info for {chat_id}: {e}")
                response += f"- Unknown channel\n  ID: {chat_id}\n  (не удалось получить данные)\n\n"
    else:
        response += "Нет каналов, добавленных вручную.\n\n"

    # Добавляем каналы где бот админ (из истории)
    admin_channels = []
    for chat_id in active_chats.keys():
        if chat_id in monitored_channels:
            continue  # Уже показан
        try:
            chat = await message.bot.get_chat(chat_id)
            if chat.type in ['supergroup', 'channel']:
                admins = await message.bot.get_chat_administrators(chat_id)
                is_admin = any(admin.user.id == bot_id for admin in admins)
                if is_admin:
                    admin_channels.append((chat_id, chat.title or "Без названия", chat.type))
        except Exception as e:
            logger.debug(f"Cannot check admins for {chat_id}: {e}")

    if admin_channels:
        response += "\nГде я администратор:\n"
        for chat_id, title, chat_type in admin_channels:
            response += f"- {title}\n  ID: {chat_id}\n  Тип: {chat_type}\n\n"

    if len(admin_channels) == 0 and not monitored_channels:
        response += "Каналов не найдено.\n\n" \
                   "Бот отвечает в:\n" \
                   "- Личных чатах с allowed users\n" \
                   "- Группах и каналах, где его упоминают (@botname, skynet)\n" \
                   "- Комментариях к постам (если админ discussion group)"

    logger.info(f"Sending /channels response, length={len(response)}")
    await message.answer(response, parse_mode=None)


@router.message(Command('add_channel'))
async def cmd_add_channel(message: Message):
    """Добавляет канал в список мониторинга"""
    if not is_allowed_user(message.from_user.id):
        return

    # Получаем ID из аргументов
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "Использование: /add_channel <channel_id>\n\n"
            "Пример: /add_channel -1002952715643"
        )
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("Ошибка: ID канала должен быть числом")
        return

    from claude_client import ClaudeClient
    claude = ClaudeClient()

    if claude.add_channel(chat_id):
        await message.answer(f"[OK] Канал {chat_id} добавлен в список мониторинга!", parse_mode=None)

        # Пытаемся получить название канала
        try:
            chat = await message.bot.get_chat(chat_id)
            title = chat.title or "Без названия"
            await message.answer(f"Название: {title}\nТип: {chat.type}", parse_mode=None)
        except Exception as e:
            logger.warning(f"Cannot get chat info for {chat_id}: {e}")
    else:
        await message.answer(f"[WARN] Канал {chat_id} уже в списке мониторинга", parse_mode=None)


@router.message(Command('remove_channel'))
async def cmd_remove_channel(message: Message):
    """Удаляет канал из списка мониторинга"""
    if not is_allowed_user(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "Использование: /remove_channel <channel_id>\n\n"
            "Пример: /remove_channel -1002952715643"
        )
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("Ошибка: ID канала должен быть числом")
        return

    from claude_client import ClaudeClient
    claude = ClaudeClient()

    if claude.remove_channel(chat_id):
        await message.answer(f"[OK] Канал {chat_id} удален из списка мониторинга!", parse_mode=None)
    else:
        await message.answer(f"[WARN] Канал {chat_id} не найден в списке мониторинга", parse_mode=None)


@router.message(Command('user_add'))
async def cmd_user_add(message: Message):
    """Добавляет пользователя в список разрешенных (только в личке)"""
    logger.info(f"/user_add command from user {message.from_user.id}, text: {message.text}")

    # Проверяем что это личный чат
    if message.chat.type != 'private':
        await message.answer("Эта команда доступна только в личных сообщениях", parse_mode=None)
        return

    if not is_allowed_user(message.from_user.id):
        logger.warning(f"User {message.from_user.id} is not allowed to use /user_add")
        await message.answer("У вас нет доступа к этой команде", parse_mode=None)
        return

    args = message.text.split()
    logger.info(f"Parsed args: {args}")
    if len(args) < 2:
        await message.answer(
            "Использование: /user_add <user_id>\n\n"
            "Пример: /user_add 123456789"
        )
        return

    try:
        user_id = int(args[1])
        logger.info(f"Parsed user_id: {user_id}")
    except ValueError as e:
        logger.error(f"Failed to parse user_id from '{args[1]}': {e}")
        await message.answer("Ошибка: ID пользователя должен быть числом")
        return

    result = claude.add_user(user_id)
    logger.info(f"add_user({user_id}) returned: {result}")

    if result:
        await message.answer(f"[OK] Пользователь {user_id} добавлен в список разрешенных!", parse_mode=None)
    else:
        await message.answer(f"[WARN] Пользователь {user_id} уже в списке разрешенных", parse_mode=None)


@router.message(Command('user_del'))
async def cmd_user_del(message: Message):
    """Удаляет пользователя из списка разрешенных (только в личке)"""
    # Проверяем что это личный чат
    if message.chat.type != 'private':
        await message.answer("Эта команда доступна только в личных сообщениях", parse_mode=None)
        return

    if not is_allowed_user(message.from_user.id):
        await message.answer("У вас нет доступа к этой команде", parse_mode=None)
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "Использование: /user_del <user_id>\n\n"
            "Пример: /user_del 123456789"
        )
        return

    try:
        user_id = int(args[1])
    except ValueError:
        await message.answer("Ошибка: ID пользователя должен быть числом")
        return

    if claude.remove_user(user_id):
        await message.answer(f"[OK] Пользователь {user_id} удален из списка разрешенных!", parse_mode=None)
    else:
        await message.answer(f"[WARN] Пользователь {user_id} не найден в списке разрешенных", parse_mode=None)


@router.message(Command('user_list'))
async def cmd_users_list(message: Message):
    """Список разрешенных пользователей (только в личке)"""
    # Проверяем что это личный чат
    if message.chat.type != 'private':
        await message.answer("Эта команда доступна только в личных сообщениях", parse_mode=None)
        return

    if not is_allowed_user(message.from_user.id):
        await message.answer("У вас нет доступа к этой команде", parse_mode=None)
        return

    allowed = claude.get_allowed_users()
    env_allowed = os.getenv('ALLOWED_USERS', '')

    response = "✅ Разрешенные пользователи:\n\n"

    if not allowed and not env_allowed:
        response += "Нет разрешенных пользователей.\n" \
                   "Используйте /user_add <id> чтобы добавить пользователя."

    # Пользователи из env
    if env_allowed:
        response += "Из окружения (ALLOWED_USERS):\n"
        for uid in env_allowed.split(','):
            response += f"- {uid}\n"
        response += "\n"

    # Пользователи из users.json
    if allowed:
        response += "Из users.json:\n"
        for uid in sorted(allowed):
            response += f"- {uid}\n"

    await message.answer(response, parse_mode=None)


@router.message(F.text, lambda msg: not msg.text.startswith('/'))
async def handle_message(message: Message):
    # Детальное логирование для отладки
    logger.info(f"📩 Message received:")
    logger.info(f"  user.id={message.from_user.id}, user.name={message.from_user.full_name}")
    logger.info(f"  chat.id={message.chat.id}, chat.type={message.chat.type}, chat.title={getattr(message.chat, 'title', 'N/A')}")
    logger.info(f"  text='{message.text}'")
    logger.info(f"  entities={message.entities}")

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
        user_id = message.from_user.id

        response = await claude.get_response(chat_id, text, user_name, user_id)
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
