"""utils/helpers.py — Shared helper utilities."""

import asyncio
import time
from typing import Optional
from pyrogram import Client
from pyrogram.types import Message, User
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import RPCError

# ── Admin status cache ────────────────────────────────────────────────────────
_admin_cache: dict[tuple[int, int], tuple[bool, float]] = {}
_ADMIN_CACHE_TTL = 300  # 5 minutes


def invalidate_admin_cache(chat_id: int, user_id: int) -> None:
    _admin_cache.pop((chat_id, user_id), None)


def mention_html(user: User) -> str:
    name = user.first_name or str(user.id)
    if user.last_name:
        name += f" {user.last_name}"
    return f'<a href="tg://user?id={user.id}">{name}</a>'


async def safe_delete(message: Message) -> None:
    try:
        await message.delete()
    except RPCError:
        pass


async def auto_delete(message: Message, delay: int) -> None:
    if delay <= 0:
        return
    await asyncio.sleep(delay)
    await safe_delete(message)


async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    key = (chat_id, user_id)
    cached = _admin_cache.get(key)
    if cached is not None:
        result, expires_at = cached
        if time.monotonic() < expires_at:
            return result
    try:
        member = await client.get_chat_member(chat_id, user_id)
        result = member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except RPCError:
        result = False
    _admin_cache[key] = (result, time.monotonic() + _ADMIN_CACHE_TTL)
    return result


def user_link(user: User) -> str:
    return mention_html(user)


def admin_link(user: User) -> str:
    return mention_html(user)
