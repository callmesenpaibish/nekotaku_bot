"""handlers/locks.py — Lock/unlock content types via group permissions + per-user restrict."""

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import RPCError
from pyrogram.handlers import MessageHandler

from database.engine import AsyncSessionLocal
from database.repository import get_group_settings, update_group_settings
from services.moderation_service import apply_group_lock, restrict_user_content
from utils.decorators import group_admin_only, group_only
from utils.helpers import auto_delete, mention_html
from handlers.errors import handle_errors

VALID_LOCKS = {"link", "sticker", "image", "video", "audio", "document", "forward"}

# forward is handled at message level (Telegram has no permission for it)
PERMISSION_LOCKS = VALID_LOCKS - {"forward"}


def _parse_lock_type(args: list) -> tuple:
    if not args:
        return None, "❌ Specify a type. Valid: " + ", ".join(sorted(VALID_LOCKS))
    lt = args[0].lower()
    if lt not in VALID_LOCKS:
        return None, f"❌ Unknown type <code>{lt}</code>. Valid: " + ", ".join(sorted(VALID_LOCKS))
    return lt, None


async def _reply_auto(message: Message, text: str, delay: int = 5) -> None:
    msg = await message.reply(text)
    asyncio.create_task(auto_delete(msg, delay))
    asyncio.create_task(auto_delete(message, 3))


@handle_errors
@group_admin_only
@group_only
async def cmd_lock(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    lock_type, err = _parse_lock_type(args)
    if err:
        await _reply_auto(message, err)
        return

    chat_id = message.chat.id
    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat_id)
        locked = set((settings.locked_types or "").split(","))
        locked.discard("")
        locked.add(lock_type)
        await update_group_settings(session, chat_id, locked_types=",".join(locked))

    # Apply group-wide permission for permission-backed locks
    if lock_type in PERMISSION_LOCKS:
        ok = await apply_group_lock(client, chat_id, locked & PERMISSION_LOCKS)
        if not ok:
            await _reply_auto(message,
                f"⚠️ <b>{lock_type}</b> locked in DB but could not set group permissions. "
                "Make sure I have 'Restrict Members' rights.")
            return

    note = " (Telegram enforces this — members physically cannot send it.)" if lock_type in PERMISSION_LOCKS else " (messages will be deleted on detection)"
    await _reply_auto(message, f"🔒 <b>{lock_type}</b> is now locked.{note}")


@handle_errors
@group_admin_only
@group_only
async def cmd_unlock(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    lock_type, err = _parse_lock_type(args)
    if err:
        await _reply_auto(message, err)
        return

    chat_id = message.chat.id
    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat_id)
        locked = set((settings.locked_types or "").split(","))
        locked.discard("")
        locked.discard(lock_type)
        await update_group_settings(session, chat_id, locked_types=",".join(locked))

    if lock_type in PERMISSION_LOCKS:
        await apply_group_lock(client, chat_id, locked & PERMISSION_LOCKS)

    await _reply_auto(message, f"🔓 <b>{lock_type}</b> is now unlocked.")


@handle_errors
@group_admin_only
@group_only
async def cmd_locks(client: Client, message: Message) -> None:
    chat_id = message.chat.id
    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat_id)
    locked = set((settings.locked_types or "").split(","))
    locked.discard("")

    lines = ["🔒 <b>Current Locks</b>\n"]
    for ltype in sorted(VALID_LOCKS):
        icon = "🔒" if ltype in locked else "🔓"
        how = "(permission)" if ltype in PERMISSION_LOCKS else "(auto-delete)"
        lines.append(f"{icon} {ltype} <i>{how}</i>")

    msg = await message.reply("\n".join(lines))
    asyncio.create_task(auto_delete(msg, 12))
    asyncio.create_task(auto_delete(message, 3))


@handle_errors
@group_admin_only
@group_only
async def cmd_restrict(client: Client, message: Message) -> None:
    """
    /restrict @user sticker[,image,video,...]
    Restrict a specific member from sending certain content types.
    """
    args = message.command[1:] if message.command else []
    reply = message.reply_to_message

    if reply and reply.from_user:
        target = reply.from_user
        content_arg = args[0] if args else None
    elif len(args) >= 2:
        identifier = args[0]
        content_arg = args[1]
        try:
            uid = int(identifier) if identifier.lstrip("-").isdigit() else identifier
            member = await client.get_chat_member(message.chat.id, uid)
            target = member.user
        except RPCError:
            await _reply_auto(message, "❌ User not found.")
            return
    else:
        await _reply_auto(message,
            "❌ Usage: <code>/restrict @user sticker</code> or reply + <code>/restrict sticker</code>\n"
            f"Valid types: {', '.join(sorted(VALID_LOCKS - {'forward'}))}",
        )
        return

    if not content_arg:
        await _reply_auto(message,
            f"❌ Specify content type(s): {', '.join(sorted(VALID_LOCKS - {'forward'}))}"
        )
        return

    types = {t.strip().lower() for t in content_arg.split(",") if t.strip().lower() in PERMISSION_LOCKS}
    if not types:
        await _reply_auto(message,
            f"❌ No valid types. Valid: {', '.join(sorted(PERMISSION_LOCKS))}"
        )
        return

    ok = await restrict_user_content(client, message.chat.id, target, types, admin=message.from_user)
    if ok:
        await _reply_auto(
            message,
            f"🔒 {mention_html(target)} can no longer send: <b>{', '.join(types)}</b>."
        )
    else:
        await _reply_auto(message, "❌ Failed to restrict user. Check my permissions.")


@handle_errors
@group_admin_only
@group_only
async def cmd_unrestrict(client: Client, message: Message) -> None:
    """
    /unrestrict @user — Restore a user's content permissions to group defaults.
    """
    args = message.command[1:] if message.command else []
    reply = message.reply_to_message

    if reply and reply.from_user:
        target = reply.from_user
    elif args:
        identifier = args[0]
        try:
            uid = int(identifier) if identifier.lstrip("-").isdigit() else identifier
            member = await client.get_chat_member(message.chat.id, uid)
            target = member.user
        except RPCError:
            await _reply_auto(message, "❌ User not found.")
            return
    else:
        await _reply_auto(message, "❌ Reply to a user or provide @username / user ID.")
        return

    # Restore permissions to group defaults (no custom restrictions)
    from pyrogram.types import ChatPermissions
    try:
        await client.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_invite_users=True,
            ),
        )
        await _reply_auto(message, f"🔓 {mention_html(target)}'s restrictions lifted.")
    except RPCError as e:
        await _reply_auto(message, f"❌ Failed: {e}")


def register(app: Client) -> None:
    app.add_handler(MessageHandler(cmd_lock,        filters.command("lock")        & filters.group))
    app.add_handler(MessageHandler(cmd_unlock,      filters.command("unlock")      & filters.group))
    app.add_handler(MessageHandler(cmd_locks,       filters.command("locks")       & filters.group))
    app.add_handler(MessageHandler(cmd_restrict,    filters.command("restrict")    & filters.group))
    app.add_handler(MessageHandler(cmd_unrestrict,  filters.command("unrestrict")  & filters.group))
