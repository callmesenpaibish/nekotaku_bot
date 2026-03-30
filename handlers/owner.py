"""handlers/owner.py — Owner-only tools: admin access management panel."""

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

import config as cfg
from database.engine import AsyncSessionLocal
from database.repository import (
    add_allowed_admin, remove_allowed_admin,
    list_allowed_admins, get_allowed_admin,
)
from keyboards.menus import admin_panel_menu
from utils.decorators import owner_only  # <--- This import MUST stay at the top

VALID_TIERS = ("full", "limited", "group_only", "readonly")
TIER_LABELS = {
    "full":       "Full private panel",
    "limited":    "Limited private access",
    "group_only": "Group commands only",
    "readonly":   "Help / read-only",
}

async def _reply(update: Update, text: str) -> None:
    """Helper to reply with HTML."""
    await update.effective_message.reply_text(text, parse_mode="HTML")

@owner_only
async def cmd_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Open the owner admin management panel."""
    await update.effective_message.reply_text(
        "👑 <b>Admin Access Panel</b>\n\n"
        "Manage which users have private-chat bot access.",
        parse_mode="HTML",
        reply_markup=admin_panel_menu(),
    )

@owner_only
async def cmd_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /addadmin @user|user_id tier
    Or reply to a user: /addadmin tier
    """
    args = context.args
    reply = update.message.reply_to_message

    # 1. Determine target user and tier
    if reply:
        target_user = reply.from_user
        user_id = target_user.id
        username = target_user.username or target_user.first_name
        tier = args[0].lower() if args else "limited" # Default to limited if not specified
    elif len(args) >= 2:
        identifier, tier = args[0], args[1].lower()
        user_id = None
        username = identifier
        
        if identifier.lstrip("-").isdigit():
            user_id = int(identifier)
            try:
                chat = await context.bot.get_chat(user_id)
                username = getattr(chat, "username", None) or chat.first_name
            except Exception:
                username = f"User:{user_id}"
        else:
            try:
                chat = await context.bot.get_chat(identifier)
                user_id = chat.id
                username = getattr(chat, "username", None) or identifier
            except Exception as e:
                await _reply(update, f"❌ <b>Chat not found.</b>\nTarget must start the bot first if using a username.\nError: {e}")
                return
    else:
        await _reply(update, "❌ <b>Usage:</b>\nReply to someone: <code>/addadmin full</code>\nOr: <code>/addadmin @user full</code>")
        return

    if tier not in VALID_TIERS:
        await _reply(update, f"❌ Invalid tier. Choose: {', '.join(VALID_TIERS)}")
        return

    # 2. Save to DB
    async with AsyncSessionLocal() as session:
        await add_allowed_admin(session, user_id=user_id, tier=tier, added_by=cfg.OWNER_ID)

    await _reply(
        update,
        f"✅ <b>{username}</b> added with tier <code>{tier}</code>.\n"
        f"<i>Note: If they haven't started the bot, they must do so to access the panel.</i>"
    )

@owner_only
async def cmd_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/removeadmin @user|user_id"""
    args = context.args
    reply = update.message.reply_to_message
    
    if reply:
        user_id = reply.from_user.id
    elif args:
        identifier = args[0]
        if identifier.lstrip("-").isdigit():
            user_id = int(identifier)
        else:
            try:
                chat = await context.bot.get_chat(identifier)
                user_id = chat.id
            except Exception:
                await _reply(update, "❌ Could not resolve username. Try using their User ID.")
                return
    else:
        await _reply(update, "❌ Usage: Reply to a user or provide <code>@username</code> / <code>user_id</code>")
        return

    async with AsyncSessionLocal() as session:
        removed = await remove_allowed_admin(session, user_id)

    if removed:
        await _reply(update, f"✅ User <code>{user_id}</code> removed from admins.")
    else:
        await _reply(update, f"❌ User <code>{user_id}</code> not found in admin list.")

@owner_only
async def cmd_list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with AsyncSessionLocal() as session:
        admins = await list_allowed_admins(session)

    if not admins:
        await _reply(update, "📋 No allowed admins configured yet.")
        return

    lines = ["📋 <b>Allowed Admins</b>\n"]
    for a in admins:
        lines.append(f"• <code>{a.user_id}</code> — <b>{a.tier}</b> ({TIER_LABELS.get(a.tier, a.tier)})")
    await _reply(update, "\n".join(lines))

async def owner_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not update.effective_user or update.effective_user.id != cfg.OWNER_ID:
        await query.answer("⛔ Owner only.", show_alert=True)
        return

    data = query.data
    if data == "oadmin:close":
        await query.delete_message()
    elif data == "oadmin:list":
        # ... (keep your existing list logic here)
        pass
    elif data == "oadmin:back":
        await query.edit_message_text(
            "👑 <b>Admin Access Panel</b>\n\nManage which users have private-chat bot access.",
            parse_mode="HTML",
            reply_markup=admin_panel_menu(),
        )

def register(application) -> None:
    application.add_handler(CommandHandler("adminpanel",   cmd_admin_panel))
    application.add_handler(CommandHandler("addadmin",      cmd_add_admin))
    application.add_handler(CommandHandler("removeadmin",   cmd_remove_admin))
    application.add_handler(CommandHandler("listadmins",    cmd_list_admins))
    application.add_handler(CallbackQueryHandler(owner_panel_callback, pattern=r"^oadmin:"))
