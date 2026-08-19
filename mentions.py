import logging

from aiogram.types import Message

logger = logging.getLogger(__name__)


async def is_mention(message: Message) -> bool:
    """Проверяет упоминание бота в сообщении"""
    if not message.text:
        return False

    bot_info = await message.bot.me()
    bot_username = bot_info.username
    text_lower = message.text.lower()

    # Проверка через entities (наиболее надёжный способ)
    if getattr(message, 'entities', None):
        for entity in message.entities:
            if entity.type == "mention":
                mentioned_text = message.text[entity.offset:entity.offset + entity.length]
                if mentioned_text.lower() == f'@{bot_username}'.lower():
                    logger.info(f"mention: found @ mention via entities: {mentioned_text}")
                    return True

    is_mention_username = f'@{bot_username}'.lower() in text_lower
    is_mention_username_no_at = bot_username.lower() in text_lower
    is_mention_name = 'skynet' in text_lower or 'скайнет' in text_lower

    logger.info(
        f"mention check: username='{bot_username}', text='{message.text[:50]}', "
        f"mention_username={is_mention_username}, mention_no_at={is_mention_username_no_at}, "
        f"mention_name={is_mention_name}"
    )

    return is_mention_username or is_mention_username_no_at or is_mention_name
