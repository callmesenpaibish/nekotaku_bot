"""handlers/welcome.py — Welcome new members and clean up join/left messages."""

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import RPCError
from pyrogram.handlers import MessageHandler, ChatMemberUpdatedHandler

from database.engine import AsyncSessionLocal
from database.repository import get_group_settings
from utils.helpers import safe_delete, auto_delete, mention_html
from handlers.errors import handle_errors
import config as cfg


async def _send_welcome(client: Client, chat_id: int, chat_title: str, user) -> None:
    """Send the welcome message for a user. Shared by both join triggers."""
    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat_id)

    if not settings.welcome_enabled:
        return

    # ── Template message (reply-based, supports media) ────────────────────────
    if settings.welcome_msg_id and settings.welcome_msg_chat_id:
        caption = None
        if settings.welcome_text:
            try:
                caption = settings.welcome_text.format(
                    mention=mention_html(user),
                    name=user.first_name,
                    group=chat_title or "this group",
                    id=user.id,
                )
            except (KeyError, ValueError):
                caption = settings.welcome_text
        try:
            await client.copy_message(
                chat_id=chat_id,
                from_chat_id=settings.welcome_msg_chat_id,
                message_id=settings.welcome_msg_id,
                caption=caption,
            )
            return
        except RPCError:
            pass  # Fall through to text welcome

    # ── Plain text welcome ────────────────────────────────────────────────────
    welcome_text = settings.welcome_text or cfg.DEFAULT_WELCOME
    try:
        text = welcome_text.format(
            mention=mention_html(user),
            name=user.first_name,
            group=chat_title or "this group",
            id=user.id,
        )
    except (KeyError, ValueError):
        text = welcome_text

    await client.send_message(chat_id=chat_id, text=text)


@handle_errors
async def handle_new_members(client: Client, message: Message) -> None:
    """
    Handles new_chat_members service messages — fires reliably for all bots.
    Sends the welcome message and optionally deletes the join service message.
    """
    chat = message.chat
    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat.id)

    for user in (message.new_chat_members or []):
        if user.is_bot:
            continue
        if settings.welcome_enabled:
            await _send_welcome(client, chat.id, chat.title, user)

    if settings.delete_join_msg:
        asyncio.create_task(auto_delete(message, settings.delete_cmd_delay))


@handle_errors
async def handle_member_updated(client: Client, member: ChatMemberUpdated) -> None:
    """
    ChatMemberUpdatedHandler — fires when the bot is admin.
    Avoids duplicate welcome if the join service message already fired it.
    """
    # We rely on handle_new_members for welcome; this handler is for future use
    pass


@handle_errors
async def handle_left_member(client: Client, message: Message) -> None:
    chat = message.chat
    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat.id)

    if settings.delete_left_msg:
        asyncio.create_task(auto_delete(message, settings.delete_cmd_delay))


def register(app: Client) -> None:
    app.add_handler(
        MessageHandler(
            handle_new_members,
            filters.group & filters.new_chat_members,
        )
    )
    app.add_handler(
        MessageHandler(
            handle_left_member,
            filters.group & filters.left_chat_member,
        )
    )
    app.add_handler(ChatMemberUpdatedHandler(handle_member_updated))
