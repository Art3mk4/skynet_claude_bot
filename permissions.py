import logging
import os

from aiogram.filters import Filter
from aiogram.types import Message

from claude_client import ClaudeClient

logger = logging.getLogger(__name__)


def is_allowed_user(user_id: int, claude: ClaudeClient) -> bool:
    """Проверяет, разрешён ли пользователь (env + users.json)"""
    allowed_env = os.getenv('ALLOWED_USERS', '')
    if allowed_env and str(user_id) in allowed_env.split(','):
        logger.info(f"is_allowed_user({user_id}): allowed via env")
        return True

    if claude.is_user_allowed(user_id):
        logger.info(f"is_allowed_user({user_id}): allowed via users.json")
        return True

    logger.info(f"is_allowed_user({user_id}): not allowed")
    return False


class AllowedUserFilter(Filter):
    """Filter для проверки разрешённых пользователей на уровне роутера"""

    async def __call__(self, message: Message, claude: ClaudeClient) -> bool:
        return is_allowed_user(message.from_user.id, claude)
