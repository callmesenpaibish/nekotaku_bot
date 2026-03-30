"""middleware/permissions.py — Role resolution for incoming updates."""

from enum import IntEnum
from typing import Optional
from pyrogram import Client
from pyrogram.types import Message, CallbackQuery
from pyrogram.enums import ChatType

import config as cfg
from database.engine import AsyncSessionLocal
from database.repository import get_allowed_admin
from utils.helpers import is_admin


class Role(IntEnum):
    OWNER = 4
    FULL_ADMIN = 3
    LIMITED_ADMIN = 2
    GROUP_ONLY_ADMIN = 1
    USER = 0


async def resolve_role(client: Client, user_id: int, chat_id: Optional[int] = None, chat_type: Optional[str] = None) -> Role:
    if user_id == cfg.OWNER_ID:
        return Role.OWNER

    async with AsyncSessionLocal() as session:
        allowed = await get_allowed_admin(session, user_id)

    if allowed:
        tier_map = {
            "full": Role.FULL_ADMIN,
            "limited": Role.LIMITED_ADMIN,
            "group_only": Role.GROUP_ONLY_ADMIN,
            "readonly": Role.USER,
        }
        return tier_map.get(allowed.tier, Role.USER)

    if chat_id and chat_type and chat_type != "private":
        if await is_admin(client, chat_id, user_id):
            return Role.GROUP_ONLY_ADMIN

    return Role.USER


def can_use_private_panel(role: Role) -> bool:
    return role in (Role.OWNER, Role.FULL_ADMIN)


def can_use_limited_private(role: Role) -> bool:
    return role >= Role.LIMITED_ADMIN
