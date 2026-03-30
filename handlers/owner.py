"""handlers/owner.py — Owner-only tools: admin access management panel."""

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from pyrogram.errors import RPCError
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

import config as cfg
from database.engine import AsyncSessionLocal
from database.repository import (
    add_allowed_admin, remove_allowed_admin,
    list_allowed_admins, get_allowed_admin,
)
from keyboards.menus import admin_panel_menu
from utils.decorators import owner_only
from handlers.errors import handle_errors

VALID_TIERS = ("full", "limited", "group_only", "readonly")
TIER_LABELS = {
    "full":       "Full private panel",
    "limited":    "Limited private access",
    "group_only": "Group commands only",
    "readonly":   "Help / read-only",
}


@handle_errors
@owner_only
async def cmd_admin_panel(client: Client, message: Message) -> None:
    await message.reply(
        "👑 <b>Admin Access Panel</b>\n\n"
        "Manage which users have private-chat bot access.",
        reply_markup=admin_panel_menu(),
    )


@handle_errors
@owner_only
async def cmd_add_admin(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    reply = message.reply_to_message

    if reply and reply.from_user:
        target_user = reply.from_user
        user_id = target_user.id
        username = target_user.username or target_user.first_name
        tier = args[0].lower() if args else "limited"
    elif len(args) >= 2:
        identifier, tier = args[0], args[1].lower()
        user_id = None
        username = identifier
        if identifier.lstrip("-").isdigit():
            user_id = int(identifier)
            try:
                chat = await client.get_chat(user_id)
                username = getattr(chat, "username", None) or chat.first_name
            except Exception:
                username = f"User:{user_id}"
        else:
            try:
                chat = await client.get_chat(identifier)
                user_id = chat.id
                username = getattr(chat, "username", None) or identifier
            except Exception as e:
                await message.reply(f"❌ <b>Chat not found.</b>\nError: {e}")
                return
    else:
        await message.reply("❌ <b>Usage:</b>\nReply to someone: <code>/addadmin full</code>\nOr: <code>/addadmin @user full</code>")
        return

    if tier not in VALID_TIERS:
        await message.reply(f"❌ Invalid tier. Choose: {', '.join(VALID_TIERS)}")
        return

    async with AsyncSessionLocal() as session:
        await add_allowed_admin(session, user_id=user_id, tier=tier, added_by=cfg.OWNER_ID)

    await message.reply(
        f"✅ <b>{username}</b> added with tier <code>{tier}</code>.\n"
        f"<i>Note: They must start the bot to access the panel.</i>"
    )


@handle_errors
@owner_only
async def cmd_remove_admin(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    reply = message.reply_to_message

    if reply and reply.from_user:
        user_id = reply.from_user.id
    elif args:
        identifier = args[0]
        if identifier.lstrip("-").isdigit():
            user_id = int(identifier)
        else:
            try:
                chat = await client.get_chat(identifier)
                user_id = chat.id
            except Exception:
                await message.reply("❌ Could not resolve username. Try using their User ID.")
                return
    else:
        await message.reply("❌ Usage: Reply to a user or provide <code>@username</code> / <code>user_id</code>")
        return

    async with AsyncSessionLocal() as session:
        removed = await remove_allowed_admin(session, user_id)

    if removed:
        await message.reply(f"✅ User <code>{user_id}</code> removed from admins.")
    else:
        await message.reply(f"❌ User <code>{user_id}</code> not found in admin list.")


@handle_errors
@owner_only
async def cmd_list_admins(client: Client, message: Message) -> None:
    async with AsyncSessionLocal() as session:
        admins = await list_allowed_admins(session)

    if not admins:
        await message.reply("📋 No allowed admins configured yet.")
        return

    lines = ["📋 <b>Allowed Admins</b>\n"]
    for a in admins:
        lines.append(f"• <code>{a.user_id}</code> — <b>{a.tier}</b> ({TIER_LABELS.get(a.tier, a.tier)})")
    await message.reply("\n".join(lines))


@handle_errors
async def owner_panel_callback(client: Client, callback_query: CallbackQuery) -> None:
    await callback_query.answer()

    if not callback_query.from_user or callback_query.from_user.id != cfg.OWNER_ID:
        await callback_query.answer("⛔ Owner only.", show_alert=True)
        return

    data = callback_query.data
    if data == "oadmin:close":
        await callback_query.message.delete()
    elif data == "oadmin:list":
        async with AsyncSessionLocal() as session:
            admins = await list_allowed_admins(session)
        if not admins:
            await callback_query.answer("No admins configured.", show_alert=True)
            return
        lines = ["📋 <b>Allowed Admins</b>\n"]
        for a in admins:
            lines.append(f"• <code>{a.user_id}</code> — <b>{a.tier}</b>")
        await callback_query.edit_message_text("\n".join(lines), reply_markup=admin_panel_menu())
    elif data == "oadmin:back":
        await callback_query.edit_message_text(
            "👑 <b>Admin Access Panel</b>\n\nManage which users have private-chat bot access.",
            reply_markup=admin_panel_menu(),
        )


def register(app: Client) -> None:
    app.add_handler(MessageHandler(cmd_admin_panel,   filters.command("adminpanel")))
    app.add_handler(MessageHandler(cmd_add_admin,     filters.command("addadmin")))
    app.add_handler(MessageHandler(cmd_remove_admin,  filters.command("removeadmin")))
    app.add_handler(MessageHandler(cmd_list_admins,   filters.command("listadmins")))
    app.add_handler(CallbackQueryHandler(owner_panel_callback, filters.regex(r"^oadmin:")))
