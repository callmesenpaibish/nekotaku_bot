"""services/moderation_service.py — Core moderation actions via Pyrogram."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from pyrogram import Client, raw
from pyrogram.types import User, ChatPermissions
from pyrogram.errors import RPCError

from database.engine import AsyncSessionLocal
from database.repository import add_infraction
from services.log_service import send_log

logger = logging.getLogger(__name__)

# ── Permission sets ────────────────────────────────────────────────────────────
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


def _until_ts(duration: Optional[int]) -> int:
    """Return Unix timestamp for until_date. 0 = permanent (Telegram standard)."""
    if not duration:
        return 0
    return int((datetime.now(timezone.utc) + timedelta(seconds=duration)).timestamp())


async def _raw_mute(client: Client, chat_id: int, user_id: int, until_ts: int) -> None:
    """Apply mute restriction via raw MTProto EditBanned (guarantees correct until_date)."""
    await client.invoke(
        raw.functions.channels.EditBanned(
            channel=await client.resolve_peer(chat_id),
            participant=await client.resolve_peer(user_id),
            banned_rights=raw.types.ChatBannedRights(
                until_date=until_ts,
                send_messages=True,
                send_media=True,
                send_stickers=True,
                send_gifs=True,
                send_games=True,
                send_inline=True,
                embed_links=True,
                send_polls=True,
            ),
        )
    )


async def _raw_ban(client: Client, chat_id: int, user_id: int, until_ts: int) -> None:
    """Apply full ban via raw MTProto EditBanned (view_messages=True = full ban)."""
    await client.invoke(
        raw.functions.channels.EditBanned(
            channel=await client.resolve_peer(chat_id),
            participant=await client.resolve_peer(user_id),
            banned_rights=raw.types.ChatBannedRights(
                until_date=until_ts,
                view_messages=True,
                send_messages=True,
                send_media=True,
                send_stickers=True,
                send_gifs=True,
                send_games=True,
                send_inline=True,
                embed_links=True,
                send_polls=True,
                change_info=True,
                invite_users=True,
                pin_messages=True,
            ),
        )
    )


async def _auto_unmute_task(
    client: Client,
    chat_id: int,
    user_id: int,
    duration: int,
    display_name: str,
) -> None:
    """Wait for duration then explicitly unmute the user and notify the group."""
    await asyncio.sleep(duration)
    try:
        await client.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=_FULL_PERMS,
        )
        await send_log(
            client, chat_id, "auto_unmute",
            target_user_id=user_id,
            extra=f"Timed mute expired after {duration}s",
            auto=True,
        )
        try:
            await client.send_message(
                chat_id=chat_id,
                text=f"🔊 <a href='tg://user?id={user_id}'>{display_name}</a> has been automatically unmuted.",
            )
        except Exception:
            pass
    except Exception as e:
        logger.warning("Auto-unmute failed for user %d in chat %d: %s", user_id, chat_id, e)


async def _auto_unban_task(
    client: Client,
    chat_id: int,
    user_id: int,
    duration: int,
    display_name: str,
) -> None:
    """Wait for duration then explicitly unban the user and notify the group."""
    await asyncio.sleep(duration)
    try:
        await client.unban_chat_member(chat_id=chat_id, user_id=user_id)
        await send_log(
            client, chat_id, "auto_unban",
            target_user_id=user_id,
            extra=f"Timed ban expired after {duration}s",
            auto=True,
        )
        try:
            await client.send_message(
                chat_id=chat_id,
                text=f"🔓 <a href='tg://user?id={user_id}'>{display_name}</a> has been automatically unbanned.",
            )
        except Exception:
            pass
    except Exception as e:
        logger.warning("Auto-unban failed for user %d in chat %d: %s", user_id, chat_id, e)


# ── Public API ─────────────────────────────────────────────────────────────────

async def mute_user(
    client: Client,
    chat_id: int,
    user: User,
    admin: Optional[User] = None,
    reason: Optional[str] = None,
    duration: Optional[int] = None,
    auto: bool = False,
) -> bool:
    ts = _until_ts(duration)
    try:
        await _raw_mute(client, chat_id, user.id, ts)
    except RPCError:
        # Fall back to high-level API
        try:
            if ts:
                await client.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user.id,
                    permissions=_MUTED_PERMS,
                    until_date=datetime.fromtimestamp(ts, tz=timezone.utc),
                )
            else:
                await client.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user.id,
                    permissions=_MUTED_PERMS,
                )
        except RPCError:
            return False
    except Exception:
        return False

    # Schedule explicit auto-unmute so it's guaranteed
    if duration:
        display = user.first_name or str(user.id)
        asyncio.create_task(_auto_unmute_task(client, chat_id, user.id, duration, display))

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
    ts = _until_ts(duration)
    try:
        await _raw_ban(client, chat_id, user.id, ts)
    except RPCError:
        try:
            if ts:
                await client.ban_chat_member(
                    chat_id=chat_id,
                    user_id=user.id,
                    until_date=datetime.fromtimestamp(ts, tz=timezone.utc),
                )
            else:
                await client.ban_chat_member(chat_id=chat_id, user_id=user.id)
        except RPCError:
            return False
    except Exception:
        return False

    # Schedule explicit auto-unban
    if duration:
        display = user.first_name or str(user.id)
        asyncio.create_task(_auto_unban_task(client, chat_id, user.id, duration, display))

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


async def restrict_user_content(
    client: Client,
    chat_id: int,
    user: User,
    locked_types: set,
    admin: Optional[User] = None,
) -> bool:
    """Apply per-user restrictions based on a set of locked content types."""
    perms = _build_permissions(locked_types, base_allow=True)
    try:
        await client.restrict_chat_member(
            chat_id=chat_id,
            user_id=user.id,
            permissions=perms,
        )
    except RPCError:
        return False
    await send_log(
        client, chat_id, "restrict",
        target_user_id=user.id,
        target_username=user.username,
        admin_id=admin.id if admin else None,
        admin_username=admin.username if admin else None,
        extra=f"Restricted content: {', '.join(locked_types)}",
    )
    return True


def _build_permissions(locked_types: set, base_allow: bool = True) -> ChatPermissions:
    """Build a ChatPermissions object from a set of locked content type names."""
    media_types = {"image", "video", "audio", "document"}
    no_media = bool(locked_types & media_types)
    no_other = "sticker" in locked_types
    no_preview = "link" in locked_types

    return ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=False if no_media else True,
        can_send_polls=True,
        can_send_other_messages=False if no_other else True,
        can_add_web_page_previews=False if no_preview else True,
        can_invite_users=True,
    )


async def apply_group_lock(
    client: Client,
    chat_id: int,
    locked_types: set,
) -> bool:
    """Apply group-wide ChatPermissions based on all currently locked types."""
    perms = _build_permissions(locked_types)
    try:
        await client.set_chat_permissions(chat_id=chat_id, permissions=perms)
        return True
    except RPCError:
        return False
