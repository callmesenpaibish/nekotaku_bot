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


@handle_errors
async def handle_member_update(client: Client, member: ChatMemberUpdated) -> None:
    old_status = member.old_chat_member.status if member.old_chat_member else None
    new_status = member.new_chat_member.status if member.new_chat_member else None

    if new_status is None:
        return

    user = member.new_chat_member.user
    chat = member.chat

    # New member joined
    if new_status == ChatMemberStatus.MEMBER and old_status not in (
        ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER
    ):
        async with AsyncSessionLocal() as session:
            settings = await get_group_settings(session, chat.id)

        if not settings.welcome_enabled:
            return

        # If a template message is stored, copy it; otherwise send text
        if settings.welcome_msg_id and settings.welcome_msg_chat_id:
            try:
                await client.copy_message(
                    chat_id=chat.id,
                    from_chat_id=settings.welcome_msg_chat_id,
                    message_id=settings.welcome_msg_id,
                    caption=(settings.welcome_text or "").format(
                        mention=mention_html(user),
                        name=user.first_name,
                        group=chat.title or "this group",
                        id=user.id,
                    ) if settings.welcome_text else None,
                )
                return
            except RPCError:
                pass  # Fall through to text welcome

        welcome_text = settings.welcome_text or cfg.DEFAULT_WELCOME
        text = welcome_text.format(
            mention=mention_html(user),
            name=user.first_name,
            group=chat.title or "this group",
            id=user.id,
        )
        await client.send_message(chat_id=chat.id, text=text)


@handle_errors
async def handle_service_messages(client: Client, message: Message) -> None:
    chat = message.chat
    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat.id)

    delay = settings.delete_cmd_delay

    if message.new_chat_members and settings.delete_join_msg:
        asyncio.create_task(auto_delete(message, delay))
        return

    if message.left_chat_member and settings.delete_left_msg:
        asyncio.create_task(auto_delete(message, delay))
        return


def register(app: Client) -> None:
    app.add_handler(ChatMemberUpdatedHandler(handle_member_update))
    app.add_handler(
        MessageHandler(
            handle_service_messages,
            filters.group & (filters.new_chat_members | filters.left_chat_member),
        )
    )
