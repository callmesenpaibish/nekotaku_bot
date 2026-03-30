"""services/moderation_service.py — Core moderation actions."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from telegram import Bot, Chat, ChatPermissions, User
from telegram.error import TelegramError

from database.engine import AsyncSessionLocal
from database.repository import add_infraction, log_action
from services.log_service import send_log


_MUTED_PERMS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
)

_FULL_PERMS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_change_info=False,
    can_invite_users=True,
    can_pin_messages=False,
)


async def mute_user(
    bot: Bot,
    chat_id: int,
    user: User,
    admin: Optional[User] = None,
    reason: Optional[str] = None,
    duration: Optional[int] = None,   # seconds; None = indefinite
    auto: bool = False,
) -> bool:
    until = (
        datetime.now(timezone.utc) + timedelta(seconds=duration)
        if duration
        else None
    )
    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user.id,
            permissions=_MUTED_PERMS,
            until_date=until,
        )
    except TelegramError:
        return False

    async with AsyncSessionLocal() as session:
        await add_infraction(
            session, chat_id, user.id, "mute",
            reason=reason,
            performed_by=admin.id if admin else None,
        )

    await send_log(
        bot, chat_id, "mute",
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
    bot: Bot,
    chat_id: int,
    user: User,
    admin: Optional[User] = None,
) -> bool:
    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user.id,
            permissions=_FULL_PERMS,
        )
    except TelegramError:
        return False

    await send_log(
        bot, chat_id, "unmute",
        target_user_id=user.id,
        target_username=user.username,
        admin_id=admin.id if admin else None,
        admin_username=admin.username if admin else None,
    )
    return True


async def kick_user(
    bot: Bot,
    chat_id: int,
    user: User,
    admin: Optional[User] = None,
    reason: Optional[str] = None,
    auto: bool = False,
) -> bool:
    try:
        await bot.ban_chat_member(chat_id=chat_id, user_id=user.id)
        # Kick = ban then immediately unban
        await bot.unban_chat_member(chat_id=chat_id, user_id=user.id, only_if_banned=True)
    except TelegramError:
        return False

    async with AsyncSessionLocal() as session:
        await add_infraction(
            session, chat_id, user.id, "kick",
            reason=reason,
            performed_by=admin.id if admin else None,
        )

    await send_log(
        bot, chat_id, "kick",
        target_user_id=user.id,
        target_username=user.username,
        admin_id=admin.id if admin else None,
        admin_username=admin.username if admin else None,
        reason=reason,
        auto=auto,
    )
    return True


async def ban_user(
    bot: Bot,
    chat_id: int,
    user: User,
    admin: Optional[User] = None,
    reason: Optional[str] = None,
    duration: Optional[int] = None,
    auto: bool = False,
) -> bool:
    until = (
        datetime.now(timezone.utc) + timedelta(seconds=duration)
        if duration
        else None
    )
    try:
        await bot.ban_chat_member(
            chat_id=chat_id,
            user_id=user.id,
            until_date=until,
        )
    except TelegramError:
        return False

    async with AsyncSessionLocal() as session:
        await add_infraction(
            session, chat_id, user.id, "ban",
            reason=reason,
            performed_by=admin.id if admin else None,
        )

    await send_log(
        bot, chat_id, "ban",
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
    bot: Bot,
    chat_id: int,
    user: User,
    admin: Optional[User] = None,
) -> bool:
    try:
        await bot.unban_chat_member(
            chat_id=chat_id,
            user_id=user.id,
            only_if_banned=True,
        )
    except TelegramError:
        return False

    await send_log(
        bot, chat_id, "unban",
        target_user_id=user.id,
        target_username=user.username,
        admin_id=admin.id if admin else None,
        admin_username=admin.username if admin else None,
    )
    return True
