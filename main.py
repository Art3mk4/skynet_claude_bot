import asyncio
import logging
import os

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import Update

from handlers import router as handlers_router
from commands import router as commands_router
from claude_client import ClaudeClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def log_updates(handler, event: Update, data: dict):
    """Middleware для логирования всех входящих апдейтов"""
    try:
        chat_id = None
        chat_type = None
        user_id = None
        text = None

        if event.message:
            chat_id = event.message.chat.id
            chat_type = event.message.chat.type
            user_id = event.message.from_user.id if event.message.from_user else None
            text = event.message.text[:50] if event.message.text else "[no text]"

        logger.info(
            f"Update {event.update_id}: type={event.event_type}, "
            f"chat_id={chat_id}, chat_type={chat_type}, user_id={user_id}, text={text}"
        )
    except Exception as e:
        logger.error(f"Error in middleware: {e}")
    return await handler(event, data)


async def main():
    load_dotenv()

    bot_token = os.getenv('TG_TOKEN')
    if not bot_token:
        raise ValueError("TG_TOKEN not found in environment")

    # Tor SOCKS5 прокси с fallback
    proxy = os.getenv('TG_PROXY')
    session = None

    if proxy:
        logger.info(f"Attempting to use proxy: {proxy}")
        try:
            session = AiohttpSession(proxy=proxy)
            test_bot = Bot(token=bot_token, session=session)
            await asyncio.wait_for(test_bot.get_me(), timeout=10)
            await session.close()
            logger.info("Proxy connection successful")
        except Exception as e:
            logger.warning(f"Proxy failed ({e}), falling back to direct connection")
            session = None

    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
        session=session
    )
    dp = Dispatcher()
    dp['claude'] = ClaudeClient()
    dp.update.middleware(log_updates)
    dp.include_router(handlers_router)
    dp.include_router(commands_router)

    logger.info("Claude bot started")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"Polling error: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('Bot stopped')
