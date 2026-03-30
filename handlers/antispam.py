"""handlers/antispam.py — Anti-spam, anti-link, anti-flood, anti-forward."""

import asyncio
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters, CommandHandler

from database.engine import AsyncSessionLocal
from database.repository import get_group_settings, update_group_settings
from services.spam_service import check_flood, reset_flood, contains_link
from services.moderation_service import mute_user
from services.log_service import send_log
from utils.helpers import safe_delete, auto_delete, is_admin, mention_html
from utils.decorators import group_admin_only, group_only


async def _handle_incoming(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Main gate for all incoming group messages — runs spam/flood/link checks."""
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not msg or not user or not chat:
        return
    if chat.type == "private":
        return
    if user.is_bot:
        return

    # Skip admins
    if await is_admin(chat, user.id, context):
        return

    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat.id)

    # ── Flood check ──────────────────────────────────────────────────────────
    if settings.flood_enabled:
        flooded = check_flood(
            chat.id, user.id,
            rate=settings.flood_rate,
            window=settings.flood_window,
        )
        if flooded:
            reset_flood(chat.id, user.id)
            await safe_delete(msg)
            duration = settings.spam_mute_duration
            ok = await mute_user(
                context.bot, chat.id, user,
                reason="Flood protection triggered",
                duration=duration,
                auto=True,
            )
            if ok:
                notif = await context.bot.send_message(
                    chat_id=chat.id,
                    text=(
                        f"🚫 {mention_html(user)} has been muted for flooding.\n"
                        f"Duration: {duration // 60}m"
                    ),
                    parse_mode="HTML",
                )
                asyncio.create_task(auto_delete(notif, settings.delete_cmd_delay))
            return

    # ── Anti-link check ──────────────────────────────────────────────────────
    text = msg.text or msg.caption or ""
    if settings.antilink_enabled and text and contains_link(text):
        await safe_delete(msg)
        notif = await context.bot.send_message(
            chat_id=chat.id,
            text=f"🔗 {mention_html(user)}, links are not allowed here.",
            parse_mode="HTML",
        )
        asyncio.create_task(auto_delete(notif, settings.delete_cmd_delay))

        await send_log(
            context.bot, chat.id, "antilink",
            target_user_id=user.id,
            target_username=user.username,
            reason="Link detected and deleted",
            auto=True,
        )
        return

    # ── Anti-forward check ───────────────────────────────────────────────────
    if settings.antiforward_enabled and msg.forward_date:
        await safe_delete(msg)
        notif = await context.bot.send_message(
            chat_id=chat.id,
            text=f"📤 {mention_html(user)}, forwarded messages are not allowed.",
            parse_mode="HTML",
        )
        asyncio.create_task(auto_delete(notif, settings.delete_cmd_delay))
        return

    # ── Locked content types ─────────────────────────────────────────────────
    locked = set((settings.locked_types or "").split(","))
    locked.discard("")

    content_map = {
        "sticker": bool(msg.sticker),
        "image":   bool(msg.photo),
        "video":   bool(msg.video),
        "audio":   bool(msg.audio or msg.voice),
        "document": bool(msg.document),
        "forward": bool(msg.forward_date),
    }

    for content_type, detected in content_map.items():
        if content_type in locked and detected:
            await safe_delete(msg)
            notif = await context.bot.send_message(
                chat_id=chat.id,
                text=f"🔒 {mention_html(user)}, <b>{content_type}s</b> are locked in this group.",
                parse_mode="HTML",
            )
            asyncio.create_task(auto_delete(notif, settings.delete_cmd_delay))
            return


# ── Auto-delete edited messages ───────────────────────────────────────────────

async def _handle_edited(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Delete edited messages after the configured delay."""
    msg = update.edited_message
    if not msg:
        return
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat.id)

    delay = settings.delete_edited_delay
    if delay <= 0:
        return

    asyncio.create_task(auto_delete(msg, delay))

    await send_log(
        context.bot, chat.id, "delete_edited",
        target_user_id=msg.from_user.id if msg.from_user else None,
        target_username=msg.from_user.username if msg.from_user else None,
        extra=f"Edited message deleted after {delay}s",
        auto=True,
    )


# ── Admin toggle commands ─────────────────────────────────────────────────────

@group_admin_only
@group_only
async def cmd_antispam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or args[0] not in ("on", "off"):
        await update.message.reply_text("Usage: /antispam on|off")
        return
    val = args[0] == "on"
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, update.effective_chat.id, antispam_enabled=val)
    msg = await update.message.reply_text(f"🛡 Anti-spam: {'✅ enabled' if val else '❌ disabled'}")
    asyncio.create_task(auto_delete(msg, 5))
    asyncio.create_task(auto_delete(update.message, 3))


@group_admin_only
@group_only
async def cmd_antilink(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or args[0] not in ("on", "off"):
        await update.message.reply_text("Usage: /antilink on|off")
        return
    val = args[0] == "on"
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, update.effective_chat.id, antilink_enabled=val)
    msg = await update.message.reply_text(f"🔗 Anti-link: {'✅ enabled' if val else '❌ disabled'}")
    asyncio.create_task(auto_delete(msg, 5))
    asyncio.create_task(auto_delete(update.message, 3))


@group_admin_only
@group_only
async def cmd_antiflood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or args[0] not in ("on", "off"):
        await update.message.reply_text("Usage: /antiflood on|off")
        return
    val = args[0] == "on"
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, update.effective_chat.id, flood_enabled=val)
    msg = await update.message.reply_text(f"🌊 Anti-flood: {'✅ enabled' if val else '❌ disabled'}")
    asyncio.create_task(auto_delete(msg, 5))
    asyncio.create_task(auto_delete(update.message, 3))


@group_admin_only
@group_only
async def cmd_floodrate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: /floodrate <number>")
        return
    val = int(args[0])
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, update.effective_chat.id, flood_rate=val)
    msg = await update.message.reply_text(f"🌊 Flood rate set to {val} messages.")
    asyncio.create_task(auto_delete(msg, 5))
    asyncio.create_task(auto_delete(update.message, 3))


@group_admin_only
@group_only
async def cmd_floodwindow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: /floodwindow <seconds>")
        return
    val = int(args[0])
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, update.effective_chat.id, flood_window=val)
    msg = await update.message.reply_text(f"🌊 Flood window set to {val}s.")
    asyncio.create_task(auto_delete(msg, 5))
    asyncio.create_task(auto_delete(update.message, 3))


def register(application) -> None:
    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & ~filters.COMMAND & ~filters.StatusUpdate.ALL,
            _handle_incoming,
        )
    )
    application.add_handler(
        MessageHandler(filters.UpdateType.EDITED_MESSAGE, _handle_edited)
    )
    application.add_handler(CommandHandler("antispam",   cmd_antispam))
    application.add_handler(CommandHandler("antilink",   cmd_antilink))
    application.add_handler(CommandHandler("antiflood",  cmd_antiflood))
    application.add_handler(CommandHandler("floodrate",  cmd_floodrate))
    application.add_handler(CommandHandler("floodwindow", cmd_floodwindow))
