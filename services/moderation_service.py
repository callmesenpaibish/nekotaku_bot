"""services/moderation_service.py — Core moderation actions via Pyrogram."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from pyrogram import Client
from pyrogram.types import User, ChatPermissions, ChatPrivileges
from pyrogram.errors import RPCError

from database.engine import AsyncSessionLocal
from database.repository import add_infraction
from services.log_service import send_log

_MUTED_PERMS = ChatPermissions(
    can_send_messages=False,
    can_send_media_messages=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
)

_FULL_PERMS = ChatPermissions(
    can_send_messages=True,
    can_send_media_messages=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_invite_users=True,
)


async def mute_user(
    client: Client,
    chat_id: int,
    user: User,
    admin: Optional[User] = None,
    reason: Optional[str] = None,
    duration: Optional[int] = None,
    auto: bool = False,
) -> bool:
    until = (
        datetime.now(timezone.utc) + timedelta(seconds=duration)
        if duration else None
    )
    try:
        await client.restrict_chat_member(
            chat_id=chat_id,
            user_id=user.id,
            permissions=_MUTED_PERMS,
            until_date=until,
        )
    except RPCError:
        return False

    async with AsyncSessionLocal() as session:
        await add_infraction(
            session, chat_id, user.id, "mute",
            reason=reason,
            performed_by=admin.id if admin else None,
        )

    await send_log(
        client, chat_id, "mute",
        target_user_id=user.id,
        target_username=user.username,
        admin_id=admin.id if admin else None,
        admin_username=admin.username if admin else None,
        reason=reason,
        duration=duration,
        auto=auto,
    )
    return True


async def unmute_user(
    client: Client,
    chat_id: int,
    user: User,
    admin: Optional[User] = None,
) -> bool:
    try:
        await client.restrict_chat_member(
            chat_id=chat_id,
            user_id=user.id,
            permissions=_FULL_PERMS,
        )
    except RPCError:
        return False

    await send_log(
        client, chat_id, "unmute",
        target_user_id=user.id,
        target_username=user.username,
        admin_id=admin.id if admin else None,
        admin_username=admin.username if admin else None,
    )
    return True


async def kick_user(
    client: Client,
    chat_id: int,
    user: User,
    admin: Optional[User] = None,
    reason: Optional[str] = None,
    auto: bool = False,
) -> bool:
    try:
        await client.ban_chat_member(chat_id=chat_id, user_id=user.id)
        await client.unban_chat_member(chat_id=chat_id, user_id=user.id)
    except RPCError:
        return False

    async with AsyncSessionLocal() as session:
        await add_infraction(
            session, chat_id, user.id, "kick",
            reason=reason,
            performed_by=admin.id if admin else None,
        )

    await send_log(
        client, chat_id, "kick",
        target_user_id=user.id,
        target_username=user.username,
        admin_id=admin.id if admin else None,
        admin_username=admin.username if admin else None,
        reason=reason,
        auto=auto,
    )
    return True


async def ban_user(
    client: Client,
    chat_id: int,
    user: User,
    admin: Optional[User] = None,
    reason: Optional[str] = None,
    duration: Optional[int] = None,
    auto: bool = False,
) -> bool:
    until = (
        datetime.now(timezone.utc) + timedelta(seconds=duration)
        if duration else None
    )
    try:
        await client.ban_chat_member(
            chat_id=chat_id,
            user_id=user.id,
            until_date=until,
        )
    except RPCError:
        return False

    async with AsyncSessionLocal() as session:
        await add_infraction(
            session, chat_id, user.id, "ban",
            reason=reason,
            performed_by=admin.id if admin else None,
        )

    await send_log(
        client, chat_id, "ban",
        target_user_id=user.id,
        target_username=user.username,
        admin_id=admin.id if admin else None,
        admin_username=admin.username if admin else None,
        reason=reason,
        duration=duration,
        auto=auto,
    )
    return True


async def unban_user(
    client: Client,
    chat_id: int,
    user: User,
    admin: Optional[User] = None,
) -> bool:
    try:
        await client.unban_chat_member(chat_id=chat_id, user_id=user.id)
    except RPCError:
        return False

    await send_log(
        client, chat_id, "unban",
        target_user_id=user.id,
        target_username=user.username,
        admin_id=admin.id if admin else None,
        admin_username=admin.username if admin else None,
    )
    return True
