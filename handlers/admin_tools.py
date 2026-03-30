"""handlers/admin_tools.py — Promote, demote, pin, adminlist commands."""

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, ChatPrivileges
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import RPCError
from pyrogram.handlers import MessageHandler

from utils.decorators import group_admin_only, group_only
from utils.helpers import auto_delete, mention_html, safe_delete
from handlers.errors import handle_errors
import config as cfg


async def _reply_auto(message: Message, text: str, delay: int = 6) -> None:
    msg = await message.reply(text)
    asyncio.create_task(auto_delete(msg, delay))
    asyncio.create_task(auto_delete(message, 3))


async def _resolve_target(client: Client, message: Message, args: list[str]):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user

    if args:
        identifier = args[0]
        try:
            uid = int(identifier) if identifier.lstrip("-").isdigit() else identifier
            member = await client.get_chat_member(message.chat.id, uid)
            return member.user
        except RPCError:
            await message.reply("❌ User not found.")
            return None

    await message.reply("❌ Reply to a user or specify @username / user ID.")
    return None


@handle_errors
@group_admin_only
@group_only
async def cmd_promote(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    target = await _resolve_target(client, message, args)
    if not target:
        return
    if target.id == cfg.OWNER_ID:
        await _reply_auto(message, "⛔ Cannot promote the bot owner via this command.")
        return
    try:
        await client.promote_chat_member(
            chat_id=message.chat.id,
            user_id=target.id,
            privileges=ChatPrivileges(
                can_manage_chat=True,
                can_delete_messages=True,
                can_restrict_members=True,
                can_invite_users=True,
                can_pin_messages=True,
            ),
        )
        await _reply_auto(message, f"⬆️ {mention_html(target)} has been promoted to admin.")
    except RPCError as e:
        await _reply_auto(message, f"❌ Failed to promote: {e}")


@handle_errors
@group_admin_only
@group_only
async def cmd_demote(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    target = await _resolve_target(client, message, args)
    if not target:
        return
    try:
        await client.promote_chat_member(
            chat_id=message.chat.id,
            user_id=target.id,
            privileges=ChatPrivileges(
                can_manage_chat=False,
                can_delete_messages=False,
                can_restrict_members=False,
                can_invite_users=False,
                can_pin_messages=False,
            ),
        )
        await _reply_auto(message, f"⬇️ {mention_html(target)} has been demoted.")
    except RPCError as e:
        await _reply_auto(message, f"❌ Failed to demote: {e}")


@handle_errors
@group_admin_only
@group_only
async def cmd_pin(client: Client, message: Message) -> None:
    if not message.reply_to_message:
        await _reply_auto(message, "❌ Reply to a message to pin it.")
        return
    args = message.command[1:] if message.command else []
    silent = bool(args and args[0].lower() == "silent")
    try:
        await client.pin_chat_message(
            chat_id=message.chat.id,
            message_id=message.reply_to_message.id,
            disable_notification=silent,
        )
        await _reply_auto(message, "📌 Message pinned." + (" (silent)" if silent else ""))
    except RPCError as e:
        await _reply_auto(message, f"❌ Could not pin: {e}")


@handle_errors
@group_admin_only
@group_only
async def cmd_unpin(client: Client, message: Message) -> None:
    try:
        await client.unpin_chat_message(chat_id=message.chat.id)
        await _reply_auto(message, "📌 Message unpinned.")
    except RPCError as e:
        await _reply_auto(message, f"❌ Could not unpin: {e}")


@handle_errors
@group_admin_only
@group_only
async def cmd_adminlist(client: Client, message: Message) -> None:
    try:
        lines = ["👮 <b>Group Admins</b>\n"]
        async for admin in client.get_chat_members(message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS):
            user = admin.user
            if user.is_bot:
                continue
            title = getattr(admin, "custom_title", None) or admin.status.name.capitalize()
            lines.append(f"• {mention_html(user)} — <i>{title}</i>")
        msg = await message.reply("\n".join(lines))
        asyncio.create_task(auto_delete(msg, 15))
        asyncio.create_task(auto_delete(message, 3))
    except RPCError as e:
        await _reply_auto(message, f"❌ Error: {e}")


def register(app: Client) -> None:
    app.add_handler(MessageHandler(cmd_promote,   filters.command("promote")   & filters.group))
    app.add_handler(MessageHandler(cmd_demote,    filters.command("demote")    & filters.group))
    app.add_handler(MessageHandler(cmd_pin,       filters.command("pin")       & filters.group))
    app.add_handler(MessageHandler(cmd_unpin,     filters.command("unpin")     & filters.group))
    app.add_handler(MessageHandler(cmd_adminlist, filters.command("adminlist") & filters.group))
