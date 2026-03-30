"""handlers/welcome.py — Welcome new members and clean up join/left messages."""

import asyncio
from telegram import Update, ChatMemberUpdated
from telegram.ext import ContextTypes, ChatMemberHandler

from database.engine import AsyncSessionLocal
from database.repository import get_group_settings
from utils.helpers import safe_delete, auto_delete, mention_html
import config as cfg


async def _welcome_new_member(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Send a welcome message when a new member joins."""
    chat_member: ChatMemberUpdated = update.chat_member
    if not chat_member:
        return

    # Only handle transitions TO member status
    old_status = chat_member.old_chat_member.status
    new_status = chat_member.new_chat_member.status
    if new_status not in ("member", "restricted") or old_status in ("member", "administrator", "creator"):
        return

    user = chat_member.new_chat_member.user
    chat = chat_member.chat

    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat.id)
        if not settings.welcome_enabled:
            return
        welcome_text = settings.welcome_text or cfg.DEFAULT_WELCOME
        delete_delay = settings.delete_cmd_delay  # reuse general delay

    text = welcome_text.format(
        mention=mention_html(user),
        name=user.full_name,
        group=chat.title or "this group",
        id=user.id,
    )

    msg = await context.bot.send_message(
        chat_id=chat.id,
        text=text,
        parse_mode="HTML",
    )
    # Welcome messages are NOT auto-deleted — they're informational


async def _handle_member_left(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle a member leaving the group."""
    chat_member: ChatMemberUpdated = update.chat_member
    if not chat_member:
        return

    old_status = chat_member.old_chat_member.status
    new_status = chat_member.new_chat_member.status

    # User left or was kicked
    if old_status in ("member", "restricted") and new_status in ("left", "kicked"):
        chat = chat_member.chat
        async with AsyncSessionLocal() as session:
            settings = await get_group_settings(session, chat.id)
            # Left notifications are handled by Telegram's system messages;
            # we log but don't send a custom message by default.


async def handle_member_update(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Route member status updates to join or leave handlers."""
    await _welcome_new_member(update, context)
    await _handle_member_left(update, context)


async def handle_service_messages(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Auto-delete Telegram service messages (join/left/pinned) and bot responses
    after a configurable delay to keep the group clean.
    """
    msg = update.effective_message
    if not msg:
        return

    chat = update.effective_chat
    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat.id)

    delay = settings.delete_cmd_delay

    # Service messages: new_chat_members, left_chat_member, pinned_message
    if msg.new_chat_members and settings.delete_join_msg:
        asyncio.create_task(auto_delete(msg, delay))
        return

    if msg.left_chat_member and settings.delete_left_msg:
        asyncio.create_task(auto_delete(msg, delay))
        return


def register(application) -> None:
    from telegram.ext import MessageHandler, filters

    application.add_handler(
        ChatMemberHandler(handle_member_update, ChatMemberHandler.CHAT_MEMBER)
    )
    application.add_handler(
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER,
            handle_service_messages,
        )
    )
