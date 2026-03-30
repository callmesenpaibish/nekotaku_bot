"""handlers/admin_tools.py — Promote, demote, pin, adminlist commands."""

import asyncio
from telegram import Update, ChatPermissions
from telegram.error import TelegramError
from telegram.ext import ContextTypes, CommandHandler

from utils.decorators import group_admin_only, group_only
from utils.helpers import auto_delete, mention_html, safe_delete
from handlers.moderation import _resolve_target
import config as cfg


async def _reply_auto(update: Update, text: str, delay: int = 6) -> None:
    msg = await update.effective_message.reply_text(text, parse_mode="HTML")
    asyncio.create_task(auto_delete(msg, delay))
    asyncio.create_task(auto_delete(update.effective_message, 3))


@group_admin_only
@group_only
async def cmd_promote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target, _ = await _resolve_target(update, context)
    if not target:
        return
    if target.id == cfg.OWNER_ID:
        await _reply_auto(update, "⛔ Cannot promote the bot owner via this command.")
        return
    try:
        await context.bot.promote_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            can_delete_messages=True,
            can_restrict_members=True,
            can_invite_users=True,
            can_pin_messages=True,
            can_manage_chat=True,
        )
        await _reply_auto(update, f"⬆️ {mention_html(target)} has been promoted to admin.")
    except TelegramError as e:
        await _reply_auto(update, f"❌ Failed to promote: {e}")


@group_admin_only
@group_only
async def cmd_demote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target, _ = await _resolve_target(update, context)
    if not target:
        return
    try:
        await context.bot.promote_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target.id,
            can_delete_messages=False,
            can_restrict_members=False,
            can_invite_users=False,
            can_pin_messages=False,
            can_manage_chat=False,
            can_post_messages=False,
            can_edit_messages=False,
        )
        await _reply_auto(update, f"⬇️ {mention_html(target)} has been demoted.")
    except TelegramError as e:
        await _reply_auto(update, f"❌ Failed to demote: {e}")


@group_admin_only
@group_only
async def cmd_pin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg.reply_to_message:
        await _reply_auto(update, "❌ Reply to a message to pin it.")
        return
    silent = bool(context.args and context.args[0].lower() == "silent")
    try:
        await context.bot.pin_chat_message(
            chat_id=update.effective_chat.id,
            message_id=msg.reply_to_message.message_id,
            disable_notification=silent,
        )
        await _reply_auto(update, "📌 Message pinned." + (" (silent)" if silent else ""))
    except TelegramError as e:
        await _reply_auto(update, f"❌ Could not pin: {e}")


@group_admin_only
@group_only
async def cmd_unpin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await context.bot.unpin_chat_message(chat_id=update.effective_chat.id)
        await _reply_auto(update, "📌 Message unpinned.")
    except TelegramError as e:
        await _reply_auto(update, f"❌ Could not unpin: {e}")


@group_admin_only
@group_only
async def cmd_adminlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        admins = await context.bot.get_chat_administrators(update.effective_chat.id)
        lines = ["👮 <b>Group Admins</b>\n"]
        for admin in admins:
            user = admin.user
            if user.is_bot:
                continue
            title = getattr(admin, "custom_title", None) or admin.status.capitalize()
            lines.append(f"• {mention_html(user)} — <i>{title}</i>")
        msg = await update.effective_message.reply_text(
            "\n".join(lines), parse_mode="HTML"
        )
        asyncio.create_task(auto_delete(msg, 15))
        asyncio.create_task(auto_delete(update.effective_message, 3))
    except TelegramError as e:
        await _reply_auto(update, f"❌ Error: {e}")


def register(application) -> None:
    application.add_handler(CommandHandler("promote",   cmd_promote))
    application.add_handler(CommandHandler("demote",    cmd_demote))
    application.add_handler(CommandHandler("pin",       cmd_pin))
    application.add_handler(CommandHandler("unpin",     cmd_unpin))
    application.add_handler(CommandHandler("adminlist", cmd_adminlist))
