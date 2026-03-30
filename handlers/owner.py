"""handlers/owner.py — Owner-only tools: admin access management panel."""

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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

TIER_DESCRIPTIONS = {
    "full":       "Full access to private panel + all group commands",
    "limited":    "Access to private panel (read-only) + most group commands",
    "group_only": "Group moderation commands only, no private panel",
    "readonly":   "Can use /help and /start only",
}


def _panel_text() -> str:
    return (
        "👑 <b>Owner Admin Panel</b>\n\n"
        "Here you can grant or revoke bot access for trusted users.\n\n"
        "<b>Access tiers:</b>\n"
        "  • <code>full</code> — Full private panel + all group commands\n"
        "  • <code>limited</code> — Private panel (read-only) + most group commands\n"
        "  • <code>group_only</code> — Group commands only, no private panel\n"
        "  • <code>readonly</code> — /help and /start only\n\n"
        "<b>Commands:</b>\n"
        "  <code>/addadmin @user full</code> — Grant access\n"
        "  <code>/removeadmin @user</code> — Revoke access\n"
        "  <code>/listadmins</code> — Show all granted users\n\n"
        "You can also reply to a user's message and run:\n"
        "  <code>/addadmin full</code>\n"
        "  <code>/removeadmin</code>"
    )


@handle_errors
@owner_only
async def cmd_admin_panel(client: Client, message: Message) -> None:
    await message.reply(_panel_text(), reply_markup=admin_panel_menu())


@handle_errors
@owner_only
async def cmd_add_admin(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    reply = message.reply_to_message

    if reply and reply.from_user:
        target_user = reply.from_user
        user_id = target_user.id
        display = f"@{target_user.username}" if target_user.username else target_user.first_name
        tier = args[0].lower() if args else "limited"
    elif len(args) >= 1:
        identifier = args[0]
        tier = args[1].lower() if len(args) >= 2 else "limited"
        user_id = None
        display = identifier
        if identifier.lstrip("-").isdigit():
            user_id = int(identifier)
            try:
                chat = await client.get_chat(user_id)
                display = f"@{chat.username}" if getattr(chat, "username", None) else chat.first_name
            except Exception:
                display = f"User ID {user_id}"
        else:
            try:
                chat = await client.get_chat(identifier)
                user_id = chat.id
                display = f"@{getattr(chat, 'username', None) or identifier}"
            except Exception as e:
                await message.reply(
                    f"❌ <b>Could not find user.</b>\n"
                    f"Try using their numeric User ID instead.\n<i>Error: {e}</i>"
                )
                return
    else:
        await message.reply(
            "❌ <b>Usage:</b>\n\n"
            "• Reply to a user's message:\n"
            "  <code>/addadmin [tier]</code>\n\n"
            "• By username or ID:\n"
            "  <code>/addadmin @username full</code>\n"
            "  <code>/addadmin 123456789 group_only</code>\n\n"
            f"Valid tiers: <code>{'</code> <code>'.join(VALID_TIERS)}</code>"
        )
        return

    if tier not in VALID_TIERS:
        await message.reply(
            f"❌ <b>Invalid tier:</b> <code>{tier}</code>\n\n"
            f"Valid options: <code>{'</code> <code>'.join(VALID_TIERS)}</code>\n\n"
            + "\n".join(f"  • <code>{t}</code> — {d}" for t, d in TIER_DESCRIPTIONS.items())
        )
        return

    async with AsyncSessionLocal() as session:
        await add_allowed_admin(session, user_id=user_id, tier=tier, added_by=cfg.OWNER_ID)

    await message.reply(
        f"✅ <b>Access granted</b>\n\n"
        f"User: {display} (<code>{user_id}</code>)\n"
        f"Tier: <code>{tier}</code> — {TIER_DESCRIPTIONS[tier]}\n\n"
        f"<i>They must send /start to the bot in private to activate access.</i>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 View All Admins", callback_data="oadmin:list")
        ]])
    )


@handle_errors
@owner_only
async def cmd_remove_admin(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    reply = message.reply_to_message

    if reply and reply.from_user:
        user_id = reply.from_user.id
        display = f"@{reply.from_user.username}" if reply.from_user.username else reply.from_user.first_name
    elif args:
        identifier = args[0]
        if identifier.lstrip("-").isdigit():
            user_id = int(identifier)
            display = f"ID {user_id}"
        else:
            try:
                chat = await client.get_chat(identifier)
                user_id = chat.id
                display = f"@{getattr(chat, 'username', None) or identifier}"
            except Exception:
                await message.reply(
                    "❌ Could not resolve username.\n"
                    "Try using their numeric User ID: <code>/removeadmin 123456789</code>"
                )
                return
    else:
        await message.reply(
            "❌ <b>Usage:</b>\n\n"
            "• Reply to a user's message: <code>/removeadmin</code>\n"
            "• By username: <code>/removeadmin @username</code>\n"
            "• By ID: <code>/removeadmin 123456789</code>"
        )
        return

    async with AsyncSessionLocal() as session:
        removed = await remove_allowed_admin(session, user_id)

    if removed:
        await message.reply(
            f"✅ <b>Access revoked</b>\n\n"
            f"User {display} (<code>{user_id}</code>) has been removed from the admin list.\n"
            f"They can no longer access the private panel."
        )
    else:
        await message.reply(
            f"❌ <b>Not found</b>\n\n"
            f"User <code>{user_id}</code> was not in the admin list.\n"
            f"Use /listadmins to see who currently has access."
        )


@handle_errors
@owner_only
async def cmd_list_admins(client: Client, message: Message) -> None:
    async with AsyncSessionLocal() as session:
        admins = await list_allowed_admins(session)

    if not admins:
        await message.reply(
            "📋 <b>No allowed admins</b>\n\n"
            "No one has been granted private access yet.\n\n"
            "To add someone:\n"
            "<code>/addadmin @username full</code>"
        )
        return

    lines = [f"📋 <b>Allowed Admins</b> ({len(admins)} total)\n"]
    for a in admins:
        tier_label = TIER_DESCRIPTIONS.get(a.tier, a.tier)
        lines.append(f"• <code>{a.user_id}</code> — <b>{a.tier}</b>\n  <i>{tier_label}</i>")

    await message.reply("\n\n".join(lines[:1]) + "\n" + "\n".join(lines[1:]))


@handle_errors
async def owner_panel_callback(client: Client, callback_query: CallbackQuery) -> None:
    if not callback_query.from_user or callback_query.from_user.id != cfg.OWNER_ID:
        await callback_query.answer("⛔ This panel is for the bot owner only.", show_alert=True)
        return

    await callback_query.answer()
    data = callback_query.data

    if data == "oadmin:close":
        await callback_query.message.delete()

    elif data == "oadmin:list":
        async with AsyncSessionLocal() as session:
            admins = await list_allowed_admins(session)
        if not admins:
            await callback_query.edit_message_text(
                "📋 <b>No allowed admins</b>\n\nNo one has been granted access yet.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("« Back", callback_data="oadmin:back")
                ]])
            )
            return
        lines = [f"📋 <b>Allowed Admins</b> ({len(admins)} total)\n"]
        for a in admins:
            tier_label = TIER_DESCRIPTIONS.get(a.tier, a.tier)
            lines.append(f"• <code>{a.user_id}</code>\n  Tier: <b>{a.tier}</b> — {tier_label}")
        await callback_query.edit_message_text(
            "\n\n".join(lines[:1]) + "\n" + "\n".join(lines[1:]),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Back", callback_data="oadmin:back")
            ]])
        )

    elif data == "oadmin:add":
        await callback_query.edit_message_text(
            "➕ <b>Add Admin</b>\n\n"
            "To grant access, send one of these in your private chat with the bot:\n\n"
            "• Reply to a user's message: <code>/addadmin full</code>\n"
            "• By username: <code>/addadmin @username group_only</code>\n"
            "• By user ID: <code>/addadmin 123456789 limited</code>\n\n"
            "<b>Tiers:</b>\n"
            + "\n".join(f"  • <code>{t}</code> — {d}" for t, d in TIER_DESCRIPTIONS.items()),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Back", callback_data="oadmin:back")
            ]])
        )

    elif data == "oadmin:remove":
        await callback_query.edit_message_text(
            "➖ <b>Remove Admin</b>\n\n"
            "To revoke access, send one of these:\n\n"
            "• Reply to their message: <code>/removeadmin</code>\n"
            "• By username: <code>/removeadmin @username</code>\n"
            "• By user ID: <code>/removeadmin 123456789</code>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("« Back", callback_data="oadmin:back")
            ]])
        )

    elif data == "oadmin:back":
        await callback_query.edit_message_text(
            _panel_text(),
            reply_markup=admin_panel_menu(),
        )


def register(app: Client) -> None:
    app.add_handler(MessageHandler(cmd_admin_panel,   filters.command("adminpanel")))
    app.add_handler(MessageHandler(cmd_add_admin,     filters.command("addadmin")))
    app.add_handler(MessageHandler(cmd_remove_admin,  filters.command("removeadmin")))
    app.add_handler(MessageHandler(cmd_list_admins,   filters.command("listadmins")))
    app.add_handler(CallbackQueryHandler(owner_panel_callback, filters.regex(r"^oadmin:")))
