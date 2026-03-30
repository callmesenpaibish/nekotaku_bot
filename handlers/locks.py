"""handlers/locks.py — Lock and unlock specific message content types."""

import asyncio
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from database.engine import AsyncSessionLocal
from database.repository import get_group_settings, update_group_settings
from utils.decorators import group_admin_only, group_only
from utils.helpers import auto_delete

VALID_LOCKS = {"link", "sticker", "image", "video", "audio", "document", "forward"}


def _parse_lock_type(args: list[str]) -> tuple[str | None, str | None]:
    if not args:
        return None, "❌ Specify a type. Valid: " + ", ".join(sorted(VALID_LOCKS))
    lock_type = args[0].lower()
    if lock_type not in VALID_LOCKS:
        return None, f"❌ Unknown type `{lock_type}`. Valid: " + ", ".join(sorted(VALID_LOCKS))
    return lock_type, None


async def _reply_auto(update: Update, text: str) -> None:
    msg = await update.effective_message.reply_text(text, parse_mode="HTML")
    asyncio.create_task(auto_delete(msg, 5))
    asyncio.create_task(auto_delete(update.effective_message, 3))


@group_admin_only
@group_only
async def cmd_lock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lock_type, err = _parse_lock_type(context.args)
    if err:
        await _reply_auto(update, err)
        return

    chat_id = update.effective_chat.id
    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat_id)
        locked = set((settings.locked_types or "").split(","))
        locked.discard("")
        locked.add(lock_type)
        await update_group_settings(session, chat_id, locked_types=",".join(locked))

    await _reply_auto(update, f"🔒 <b>{lock_type}</b> is now locked in this group.")


@group_admin_only
@group_only
async def cmd_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lock_type, err = _parse_lock_type(context.args)
    if err:
        await _reply_auto(update, err)
        return

    chat_id = update.effective_chat.id
    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat_id)
        locked = set((settings.locked_types or "").split(","))
        locked.discard("")
        locked.discard(lock_type)
        await update_group_settings(session, chat_id, locked_types=",".join(locked))

    await _reply_auto(update, f"🔓 <b>{lock_type}</b> is now unlocked.")


@group_admin_only
@group_only
async def cmd_locks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat_id)
    locked = set((settings.locked_types or "").split(","))
    locked.discard("")

    lines = ["🔒 <b>Current Locks</b>\n"]
    for ltype in sorted(VALID_LOCKS):
        icon = "🔒" if ltype in locked else "🔓"
        lines.append(f"{icon} {ltype}")

    msg = await update.effective_message.reply_text("\n".join(lines), parse_mode="HTML")
    asyncio.create_task(auto_delete(msg, 10))
    asyncio.create_task(auto_delete(update.effective_message, 3))


def register(application) -> None:
    application.add_handler(CommandHandler("lock",   cmd_lock))
    application.add_handler(CommandHandler("unlock", cmd_unlock))
    application.add_handler(CommandHandler("locks",  cmd_locks))
