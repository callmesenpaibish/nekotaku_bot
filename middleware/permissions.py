"""middleware/permissions.py — Role resolution for incoming updates."""

from enum import IntEnum
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes

import config as cfg
from database.engine import AsyncSessionLocal
from database.repository import get_allowed_admin
from utils.helpers import is_admin


class Role(IntEnum):
    OWNER = 4
    FULL_ADMIN = 3        # allowed admin: full private panel access
    LIMITED_ADMIN = 2     # allowed admin: limited private access
    GROUP_ONLY_ADMIN = 1  # group admins not in the allowed list
    USER = 0


async def resolve_role(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> Role:
    """Resolve the effective user's role for the current context."""
    user = update.effective_user
    chat = update.effective_chat
    if not user:
        return Role.USER

    if user.id == cfg.OWNER_ID:
        return Role.OWNER

    async with AsyncSessionLocal() as session:
        allowed = await get_allowed_admin(session, user.id)

    if allowed:
        tier_map = {
            "full": Role.FULL_ADMIN,
            "limited": Role.LIMITED_ADMIN,
            "group_only": Role.GROUP_ONLY_ADMIN,
            "readonly": Role.USER,
        }
        return tier_map.get(allowed.tier, Role.USER)

    # Check if they're a Telegram admin in the group
    if chat and chat.type != "private":
        if await is_admin(chat, user.id, context):
            return Role.GROUP_ONLY_ADMIN

    return Role.USER


def can_use_private_panel(role: Role) -> bool:
    return role in (Role.OWNER, Role.FULL_ADMIN)


def can_use_limited_private(role: Role) -> bool:
    return role >= Role.LIMITED_ADMIN
