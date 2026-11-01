import logging
import os

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command, CommandStart

from permissions import is_allowed_user, AllowedUserFilter
from claude_client import ClaudeClient
from news_scheduler import NewsConfigurationError, NewsScheduler

logger = logging.getLogger(__name__)
router = Router()

COMMANDS_LIST = (
    "/start - Начать\n"
    "/clear - Очистить историю диалога\n"
    "/chats - Список активных чатов с историей\n"
    "/channels - Список каналов и групп, где я администратор\n"
    "/user_list - Список разрешённых пользователей\n"
    "/user_add <id> - Добавить пользователя\n"
    "/user_del <id> - Удалить пользователя\n"
    "/add_channel <id> - Добавить канал\n"
    "/remove_channel <id> - Удалить канал\n"
    "/news_add - Добавить автопубликацию\n"
    "/news_list - Список автопубликаций\n"
    "/news_preview <id> - Предпросмотр новости\n"
    "/news_run <id> - Опубликовать сейчас\n"
    "/news_del <id> - Удалить автопубликацию\n"
    "/help - Помощь"
)

NEWS_ADD_USAGE = (
    "Использование:\n"
    "/news_add daily 09:00 <инструкция>\n"
    "/news_add weekly mon 10:00 <инструкция>"
)


async def _require_private_allowed_user(message: Message, claude: ClaudeClient) -> bool:
    """Общая проверка для команд, доступных только разрешённым пользователям в личке"""
    if message.chat.type != 'private':
        await message.answer("Эта команда доступна только в личных сообщениях")
        return False

    if not is_allowed_user(message.from_user.id, claude):
        await message.answer("У вас нет доступа к этой команде")
        return False

    return True


@router.message(CommandStart())
async def cmd_start(message: Message, claude: ClaudeClient) -> None:
    logger.info(f"/start command from user {message.from_user.id}")

    if not is_allowed_user(message.from_user.id, claude):
        logger.warning(f"User {message.from_user.id} not allowed to use /start")
        await message.answer("У вас нет доступа к этому боту")
        return

    await message.answer(
        "Привет! Я SkyNet, AI ассистент на базе Claude от Anthropic.\n\n"
        "Упомяни меня (@username или просто 'skynet') в сообщении, и я отвечу.\n"
        "Работаю в группах, каналах и комментариях к постам.\n\n"
        "Команды:\n" + COMMANDS_LIST
    )


@router.message(Command('clear'), AllowedUserFilter())
async def cmd_clear(message: Message, claude: ClaudeClient) -> None:
    logger.info(f"/clear command from user {message.from_user.id}, chat={message.chat.id}")

    chat_id = message.chat.id
    await claude.clear_history(chat_id)
    await message.answer("История диалога очищена")


@router.message(Command('help'), AllowedUserFilter())
async def cmd_help(message: Message, claude: ClaudeClient) -> None:
    logger.info(f"/help command from user {message.from_user.id}")

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
        "/user_list - Список разрешённых пользователей\n"
        "/user_add &lt;id&gt; - Добавить пользователя\n"
        "/user_del &lt;id&gt; - Удалить пользователя\n"
        "/news_add - Добавить автопубликацию\n"
        "/news_list - Список автопубликаций\n"
        "/news_preview &lt;id&gt; - Предпросмотр новости\n"
        "/news_run &lt;id&gt; - Опубликовать сейчас\n"
        "/news_del &lt;id&gt; - Удалить автопубликацию\n"
        "/help - Эта справка",
        parse_mode="HTML"
    )


@router.message(Command('chats'), AllowedUserFilter())
async def cmd_chats(message: Message, claude: ClaudeClient) -> None:
    logger.info(f"/chats command from user {message.from_user.id}")

    active_chats = claude.get_active_chats()

    if not active_chats:
        await message.answer("Нет активных чатов с историей")
        return

    response = "Список активных чатов:\n\n"
    for chat_id, msg_count in active_chats.items():
        # Определение типа чата через API (надежнее, чем по диапазону ID)
        try:
            chat = await message.bot.get_chat(chat_id)
            chat_type_map = {
                'private': 'Личный чат',
                'group': 'Группа',
                'supergroup': 'Супергруппа',
                'channel': 'Канал'
            }
            chat_type = chat_type_map.get(chat.type, f"Неизвестный ({chat.type})")
        except Exception as e:
            logger.warning(f"Cannot get chat type for {chat_id}: {e}")
            # Fallback к определению по ID только если API недоступен
            if chat_id == 0:
                chat_type = "Неизвестный тип"
            elif chat_id > 0:
                chat_type = "Личный чат"
            else:
                chat_type = "Группа/Канал"

        response += f"• Chat ID: <code>{chat_id}</code> ({chat_type})\n  Сообщений в истории: {msg_count}\n\n"

    response += "Используй /channels для просмотра мониторируемых каналов."

    await message.answer(response, parse_mode="HTML")


@router.message(Command('channels'), AllowedUserFilter())
async def cmd_channels_info(message: Message, claude: ClaudeClient) -> None:
    logger.info(f"/channels command from user {message.from_user.id}")

    monitored_channels = claude.get_monitored_channels()
    active_chats = claude.get_active_chats()

    bot_info = await message.bot.me()
    bot_id = bot_info.id

    if not monitored_channels and not active_chats:
        await message.answer(
            "Нет активных чатов и мониторируемых каналов.\n\n"
            "Для добавления канала используй:\n"
            "/add_channel &lt;channel_id&gt;",
            parse_mode="HTML"
        )
        return

    response = "Мониторируемые каналы:\n\n"

    if monitored_channels:
        response += "Добавленные вручную:\n"
        for chat_id in monitored_channels:
            try:
                chat = await message.bot.get_chat(chat_id)
                title = chat.title or "Без названия"
                response += f"- {title}\n  ID: <code>{chat_id}</code>\n  Тип: {chat.type}\n\n"
            except Exception as e:
                logger.warning(f"Cannot get chat info for {chat_id}: {e}")
                response += f"- Unknown channel\n  ID: <code>{chat_id}</code>\n  (не удалось получить данные)\n\n"
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
            response += f"- {title}\n  ID: <code>{chat_id}</code>\n  Тип: {chat_type}\n\n"

    if len(admin_channels) == 0 and not monitored_channels:
        response += "Каналов не найдено.\n\n"

    # Split message if it exceeds Telegram's limit (4096 characters)
    MAX_LENGTH = 4000  # Leave some margin
    if len(response) > MAX_LENGTH:
        parts = []
        current_part = ""
        for line in response.split('\n'):
            if len(current_part) + len(line) + 1 > MAX_LENGTH:
                parts.append(current_part)
                current_part = line + '\n'
            else:
                current_part += line + '\n'
        if current_part:
            parts.append(current_part)

        for part in parts:
            await message.answer(part, parse_mode="HTML")
    else:
        await message.answer(response, parse_mode="HTML")


@router.message(Command('add_channel'), AllowedUserFilter())
async def cmd_add_channel(message: Message, claude: ClaudeClient) -> None:
    logger.info(f"/add_channel command from user {message.from_user.id}")

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

    if await claude.add_channel(chat_id):
        await message.answer(f"[OK] Канал {chat_id} добавлен в список мониторинга!")

        try:
            chat = await message.bot.get_chat(chat_id)
            title = chat.title or "Без названия"
            await message.answer(f"Название: {title}\nТип: {chat.type}")
        except Exception as e:
            logger.warning(f"Cannot get chat info for {chat_id}: {e}")
    else:
        await message.answer(f"[WARN] Канал {chat_id} уже в списке мониторинга")


@router.message(Command('remove_channel'), AllowedUserFilter())
async def cmd_remove_channel(message: Message, claude: ClaudeClient) -> None:
    logger.info(f"/remove_channel command from user {message.from_user.id}")

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

    if await claude.remove_channel(chat_id):
        await message.answer(f"[OK] Канал {chat_id} удалён из списка мониторинга!")
    else:
        await message.answer(f"[WARN] Канал {chat_id} не найден в списке мониторинга")


@router.message(Command('user_add'))
async def cmd_user_add(message: Message, claude: ClaudeClient) -> None:
    logger.info(f"/user_add command from user {message.from_user.id}, text: {message.text}")

    if not await _require_private_allowed_user(message, claude):
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

    result = await claude.add_user(user_id, username)
    logger.info(f"add_user({user_id}) returned: {result}")

    if result:
        await message.answer(f"[OK] Пользователь {user_id} добавлен в список разрешённых!")
    else:
        await message.answer(f"[WARN] Пользователь {user_id} уже в списке разрешённых")


@router.message(Command('user_del'))
async def cmd_user_del(message: Message, claude: ClaudeClient) -> None:
    if not await _require_private_allowed_user(message, claude):
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
        await message.answer("Ошибка: ID пользователя должен быть числом")
        return

    result = await claude.remove_user(user_id)
    logger.info(f"remove_user({user_id}) returned: {result}")

    if result:
        await message.answer(f"[OK] Пользователь {user_id} удалён из списка разрешённых!")
    else:
        await message.answer(f"[WARN] Пользователь {user_id} не найден в списке разрешённых")


@router.message(Command('user_list'))
async def cmd_users_list(message: Message, claude: ClaudeClient) -> None:
    if not await _require_private_allowed_user(message, claude):
        return

    allowed = claude.get_allowed_users()
    env_allowed = os.getenv('ALLOWED_USERS', '')

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

    await message.answer(response)


def _parse_news_add_input(text: str) -> tuple[str, str, str, str]:
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        raise ValueError(NEWS_ADD_USAGE)

    schedule_type = parts[1].split()[0].lower()
    if schedule_type == 'daily':
        parts = text.split(maxsplit=3)
        if len(parts) != 4:
            raise ValueError(NEWS_ADD_USAGE)
        return schedule_type, parts[2], parts[3], ''
    if schedule_type == 'weekly':
        parts = text.split(maxsplit=4)
        if len(parts) != 5:
            raise ValueError(NEWS_ADD_USAGE)
        return schedule_type, parts[3], parts[4], parts[2].lower()
    raise ValueError(NEWS_ADD_USAGE)


async def _answer_long_text(message: Message, text: str):
    for offset in range(0, len(text), 4000):
        await message.answer(text[offset:offset + 4000], parse_mode=None)


@router.message(Command('news_add'))
async def cmd_news_add(message: Message, claude: ClaudeClient, news_scheduler: NewsScheduler) -> None:
    if not await _require_private_allowed_user(message, claude):
        return

    try:
        schedule_type, time_value, instruction, weekday = _parse_news_add_input(message.text)
        job_id = await news_scheduler.add_job(
            schedule_type=schedule_type,
            time_value=time_value,
            instruction=instruction,
            created_by=message.from_user.id,
            weekday=weekday or None,
        )
    except (ValueError, NewsConfigurationError) as error:
        await message.answer(str(error))
        return
    except Exception as error:
        logger.error(f"Cannot create scheduled news job: {error}", exc_info=True)
        await message.answer("Не удалось сохранить задание")
        return

    next_run = news_scheduler.get_next_run(job_id)
    response = f"Автопубликация создана. ID: {job_id}"
    if next_run:
        response += f"\nСледующий запуск: {next_run.strftime('%d.%m.%Y %H:%M %Z')}"
    await message.answer(response)


@router.message(Command('news_list'))
async def cmd_news_list(message: Message, claude: ClaudeClient, news_scheduler: NewsScheduler) -> None:
    if not await _require_private_allowed_user(message, claude):
        return

    jobs = news_scheduler.get_jobs()
    if not jobs:
        await message.answer("Автопубликации не настроены")
        return

    response = "Автопубликации:\n"
    for job in jobs:
        schedule = f"{job['schedule_type']} {job['time']}"
        if job['schedule_type'] == 'weekly':
            schedule = f"{job['schedule_type']} {job['weekday']} {job['time']}"
        next_run = news_scheduler.get_next_run(job['id'])
        instruction = job['instruction']
        if len(instruction) > 150:
            instruction = instruction[:147] + '...'
        response += f"\nID: {job['id']}\nРасписание: {schedule}\nИнструкция: {instruction}\n"
        if next_run:
            response += f"Следующий запуск: {next_run.strftime('%d.%m.%Y %H:%M %Z')}\n"
        if job.get('last_error'):
            response += "Последний запуск завершился ошибкой\n"

    await _answer_long_text(message, response)


@router.message(Command('news_preview'))
async def cmd_news_preview(message: Message, claude: ClaudeClient, news_scheduler: NewsScheduler) -> None:
    if not await _require_private_allowed_user(message, claude):
        return

    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /news_preview <id>")
        return

    try:
        text = await news_scheduler.preview_job(args[1])
    except ValueError as error:
        await message.answer(str(error))
        return
    except Exception as error:
        logger.error(f"Cannot preview scheduled news job {args[1]}: {error}", exc_info=True)
        await message.answer("Не удалось сгенерировать новость")
        return
    await _answer_long_text(message, text)


@router.message(Command('news_run'))
async def cmd_news_run(message: Message, claude: ClaudeClient, news_scheduler: NewsScheduler) -> None:
    if not await _require_private_allowed_user(message, claude):
        return

    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /news_run <id>")
        return

    try:
        await news_scheduler.run_now(args[1])
    except (ValueError, NewsConfigurationError) as error:
        await message.answer(str(error))
        return
    except Exception as error:
        logger.error(f"Cannot run scheduled news job {args[1]}: {error}", exc_info=True)
        await message.answer("Не удалось опубликовать новость. Автоматический повтор не выполнялся.")
        return
    await message.answer("Новость опубликована")


@router.message(Command('news_del'))
async def cmd_news_del(message: Message, claude: ClaudeClient, news_scheduler: NewsScheduler) -> None:
    if not await _require_private_allowed_user(message, claude):
        return

    args = message.text.split()
    if len(args) != 2:
        await message.answer("Использование: /news_del <id>")
        return

    try:
        removed = await news_scheduler.remove_job(args[1])
    except Exception as error:
        logger.error(f"Cannot remove scheduled news job {args[1]}: {error}", exc_info=True)
        await message.answer("Не удалось удалить задание")
        return

    if removed:
        await message.answer("Автопубликация удалена")
    else:
        await message.answer("Задание не найдено")
