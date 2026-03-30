"""handlers/locks.py — Lock and unlock specific message content types."""

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler

from database.engine import AsyncSessionLocal
from database.repository import get_group_settings, update_group_settings
from utils.decorators import group_admin_only, group_only
from utils.helpers import auto_delete
from handlers.errors import handle_errors

VALID_LOCKS = {"link", "sticker", "image", "video", "audio", "document", "forward"}


def _parse_lock_type(args: list[str]) -> tuple:
    if not args:
        return None, "❌ Specify a type. Valid: " + ", ".join(sorted(VALID_LOCKS))
    lock_type = args[0].lower()
    if lock_type not in VALID_LOCKS:
        return None, f"❌ Unknown type `{lock_type}`. Valid: " + ", ".join(sorted(VALID_LOCKS))
    return lock_type, None


async def _reply_auto(message: Message, text: str) -> None:
    msg = await message.reply(text)
    asyncio.create_task(auto_delete(msg, 5))
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

    await _reply_auto(message, f"🔒 <b>{lock_type}</b> is now locked in this group.")


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
        lines.append(f"{icon} {ltype}")

    msg = await message.reply("\n".join(lines))
    asyncio.create_task(auto_delete(msg, 10))
    asyncio.create_task(auto_delete(message, 3))


def register(app: Client) -> None:
    app.add_handler(MessageHandler(cmd_lock,   filters.command("lock")   & filters.group))
    app.add_handler(MessageHandler(cmd_unlock, filters.command("unlock") & filters.group))
    app.add_handler(MessageHandler(cmd_locks,  filters.command("locks")  & filters.group))
