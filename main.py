import os
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession
from handlers import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
            # Тестируем прокси
            session = AiohttpSession(proxy=proxy)
            test_bot = Bot(token=bot_token, session=session)
            await asyncio.wait_for(test_bot.get_me(), timeout=10)
            await test_bot.session.close()
            logger.info("✓ Proxy connection successful")
        except Exception as e:
            logger.warning(f"✗ Proxy failed ({e}), falling back to direct connection")
            session = None

    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
        session=session
    )
    dp = Dispatcher()
    dp.include_router(router)

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
