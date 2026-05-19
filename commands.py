import logging

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command, CommandStart

from permissions import is_allowed_user
from claude_client import ClaudeClient

logger = logging.getLogger(__name__)
router = Router()


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
        "/users - Список разрешённых пользователей\n"
        "/user_add <id> - Добавить пользователя\n"
        "/user_del <id> - Удалить пользователя\n"
        "/help - Помощь"
    )


@router.message(Command('clear'))
async def cmd_clear(message: Message, claude: ClaudeClient):
    if not is_allowed_user(message.from_user.id):
        return

    chat_id = message.chat.id
    claude.clear_history(chat_id)
    await message.answer("История диалога очищена")


@router.message(Command('help'))
async def cmd_help(message: Message, claude: ClaudeClient):
    if not is_allowed_user(message.from_user.id):
        return

    await message.answer(
        "Я SkyNet, AI ассистент на базе Claude.\n\n"
        "Упомяни меня в сообщении:\n"
        "• @bot\\_username что такое Python?\n"
        "• skynet, помоги с кодом\n\n"
        "Работаю в личных чатах, группах, каналах и комментариях.\n"
        "Я запоминаю контекст разговора в рамках чата.\n\n"
        "Команды:\n"
        "/clear - Очистить историю\n"
        "/chats - Список активных чатов\n"
        "/channels - Мониторируемые каналы\n"
        "/users - Список разрешённых пользователей\n"
        "/user\\_add <id> - Добавить пользователя\n"
        "/user\\_del <id> - Удалить пользователя\n"
        "/help - Эта справка",
        parse_mode="MarkdownV2"
    )


@router.message(Command('chats'))
async def cmd_chats(message: Message, claude: ClaudeClient):
    if not is_allowed_user(message.from_user.id):
        return

    active_chats = claude.get_active_chats()

    if not active_chats:
        await message.answer("Нет активных чатов с историей")
        return

    response = "Список активных чатов:\n\n"
    for chat_id, msg_count in active_chats.items():
        chat_type = "Личный чат" if chat_id > 0 else "Группа"
        response += f"• Chat ID: `{chat_id}` ({chat_type})\n  Сообщений в истории: {msg_count}\n\n"

    response += "Используй /channels для просмотра мониторируемых каналов."

    await message.answer(response)


@router.message(Command('channels'))
async def cmd_channels_info(message: Message, claude: ClaudeClient):
    if not is_allowed_user(message.from_user.id):
        return

    monitored_channels = claude.get_monitored_channels()
    active_chats = claude.get_active_chats()

    bot_info = await message.bot.me()
    bot_id = bot_info.id

    response = "Мониторируемые каналы:\n\n"

    if not monitored_channels and not active_chats:
        await message.answer(
            "Нет активных чатов и мониторируемых каналов.\n\n"
            "Для добавления канала используй:\n"
            "/add_channel <channel_id>",
            parse_mode=None
        )
        return

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

    admin_channels = []
    for chat_id in active_chats.keys():
        if chat_id in monitored_channels:
            continue
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
        response += "Каналов не найдено.\n\n"

    await message.answer(response, parse_mode=None)


@router.message(Command('add_channel'))
async def cmd_add_channel(message: Message, claude: ClaudeClient):
    if not is_allowed_user(message.from_user.id):
        return

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

    if claude.add_channel(chat_id):
        await message.answer(f"[OK] Канал {chat_id} добавлен в список мониторинга!", parse_mode=None)

        try:
            chat = await message.bot.get_chat(chat_id)
            title = chat.title or "Без названия"
            await message.answer(f"Название: {title}\nТип: {chat.type}", parse_mode=None)
        except Exception as e:
            logger.warning(f"Cannot get chat info for {chat_id}: {e}")
    else:
        await message.answer(f"[WARN] Канал {chat_id} уже в списке мониторинга", parse_mode=None)


@router.message(Command('remove_channel'))
async def cmd_remove_channel(message: Message, claude: ClaudeClient):
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

    if claude.remove_channel(chat_id):
        await message.answer(f"[OK] Канал {chat_id} удалён из списка мониторинга!", parse_mode=None)
    else:
        await message.answer(f"[WARN] Канал {chat_id} не найден в списке мониторинга", parse_mode=None)


@router.message(Command('user_add'))
async def cmd_user_add(message: Message, claude: ClaudeClient):
    logger.info(f"/user_add command from user {message.from_user.id}, text: {message.text}")

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

    try:
        chat = await message.bot.get_chat(user_id)
        username = chat.username or ""
        logger.info(f"Got username for user {user_id}: {username}")
    except Exception as e:
        logger.warning(f"Could not fetch username for user {user_id}: {e}")
        username = ""

    result = claude.add_user(user_id, username)
    logger.info(f"add_user({user_id}) returned: {result}")

    if result:
        await message.answer(f"[OK] Пользователь {user_id} добавлен в список разрешённых!", parse_mode=None)
    else:
        await message.answer(f"[WARN] Пользователь {user_id} уже в списке разрешённых", parse_mode=None)


@router.message(Command('user_del'))
async def cmd_user_del(message: Message, claude: ClaudeClient):
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
            "Пример: /user_del 123456789",
            parse_mode=None
        )
        return

    try:
        user_id = int(args[1])
        logger.info(f"Parsed user_id: {user_id}")
    except ValueError as e:
        logger.error(f"Failed to parse user_id from '{args[1]}': {e}")
        await message.answer("Ошибка: ID пользователя должен быть числом", parse_mode=None)
        return

    result = claude.remove_user(user_id)
    logger.info(f"remove_user({user_id}) returned: {result}")

    if result:
        await message.answer(f"[OK] Пользователь {user_id} удалён из списка разрешённых!", parse_mode=None)
    else:
        await message.answer(f"[WARN] Пользователь {user_id} не найден в списке разрешённых", parse_mode=None)


@router.message(Command('user_list'))
async def cmd_users_list(message: Message, claude: ClaudeClient):
    if message.chat.type != 'private':
        await message.answer("Эта команда доступна только в личных сообщениях", parse_mode=None)
        return

    if not is_allowed_user(message.from_user.id):
        await message.answer("У вас нет доступа к этой команде", parse_mode=None)
        return

    allowed = claude.get_allowed_users()
    env_allowed = __import__('os').getenv('ALLOWED_USERS', '')

    response = "Разрешённые пользователи:\n\n"

    if not allowed and not env_allowed:
        response += "Нет разрешённых пользователей.\n" \
                    "Используйте /user_add <id> чтобы добавить пользователя."

    if env_allowed:
        response += "Из окружения (ALLOWED_USERS):\n"
        for uid in env_allowed.split(','):
            response += f"- {uid}\n"
        response += "\n"

    if allowed:
        response += "Из users.json:\n"
        for uid, username in sorted(allowed.items()):
            if username:
                response += f"- {uid} (@{username})\n"
            else:
                response += f"- {uid}\n"

    await message.answer(response, parse_mode=None)
