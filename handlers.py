import logging

from aiogram import Router, F
from aiogram.types import Message

from mentions import is_mention
from permissions import is_allowed_user
from claude_client import ClaudeClient

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text, lambda msg: not msg.text.startswith('/'))
async def handle_message(message: Message, claude: ClaudeClient = None):
    logger.info(
        f"Message received: user={message.from_user.id}, "
        f"chat={message.chat.id}({message.chat.type}), text='{message.text[:80]}'"
    )

    is_private = message.chat.type == 'private'

    if is_private and not is_allowed_user(message.from_user.id):
        logger.info(f"User {message.from_user.id} not allowed, ignoring private chat")
        return

    if not is_private and not await is_mention(message):
        logger.info("Not a mention in group/channel, ignoring")
        return

    if not is_private and not is_allowed_user(message.from_user.id):
        logger.info(f"User {message.from_user.id} not allowed in group {message.chat.id}")
        return

    # Strip mention from text (case-insensitive)
    text = message.text
    bot_info = await message.bot.me()
    bot_username = bot_info.username
    text = _strip_mentions(text, bot_username)

    if not text:
        await message.answer("Да? Чем могу помочь?")
        return

    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        chat_id = message.chat.id
        user_name = message.from_user.full_name or message.from_user.username or "User"
        user_id = message.from_user.id

        response = await claude.get_response(chat_id, text, user_name, user_id)
        logger.info(f"Got response from Claude, length: {len(response)}")

        if len(response) > 4096:
            for i in range(0, len(response), 4096):
                await message.answer(response[i:i+4096])
        else:
            await message.answer(response)

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        await message.answer(f"Произошла ошибка: {str(e)}")


def _strip_mentions(text: str, bot_username: str) -> str:
    """Remove bot mention and alias keywords from text (case-insensitive)"""
    import re

    # Remove @username
    text = re.sub(
        rf'@{re.escape(bot_username)}\b', '', text, flags=re.IGNORECASE
    )
    # Remove alias keywords (standalone words)
    text = re.sub(r'\bskynet\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bскайнет\b', '', text, flags=re.IGNORECASE)

    # Clean up leftover punctuation and extra spaces
    text = re.sub(r'[,\s]+', ' ', text).strip()
    return text
