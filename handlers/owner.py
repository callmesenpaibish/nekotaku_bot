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
from utils.decorators import owner_only

VALID_TIERS = ("full", "limited", "group_only", "readonly")
TIER_LABELS = {
    "full":       "Full private panel",
    "limited":    "Limited private access",
    "group_only": "Group commands only",
    "readonly":   "Help / read-only",
}


async def _reply(update: Update, text: str) -> None:
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
    /addadmin @user full|limited|group_only|readonly
    """
    args = context.args
    if len(args) < 2:
        await _reply(update, "❌ Usage: /addadmin @user|user_id full|limited|group_only|readonly")
        return
    identifier, tier = args[0], args[1].lower()
    if tier not in VALID_TIERS:
        await _reply(update, f"❌ Invalid tier. Choose: {', '.join(VALID_TIERS)}")
        return

    try:
        if identifier.lstrip("-").isdigit():
            user = await context.bot.get_chat(int(identifier))
            user_id = user.id
            username = getattr(user, "username", None) or str(user_id)
        else:
            chat = await context.bot.get_chat(identifier)
            user_id = chat.id
            username = getattr(chat, "username", None) or str(user_id)
    except Exception as e:
        await _reply(update, f"❌ Could not find user: {e}")
        return

    async with AsyncSessionLocal() as session:
        await add_allowed_admin(session, user_id=user_id, tier=tier, added_by=cfg.OWNER_ID)

    await _reply(
        update,
        f"✅ <b>{username}</b> added with tier <code>{tier}</code> ({TIER_LABELS[tier]})."
    )


@owner_only
async def cmd_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /removeadmin @user|user_id
    """
    args = context.args
    if not args:
        await _reply(update, "❌ Usage: /removeadmin @user|user_id")
        return
    identifier = args[0]
    try:
        if identifier.lstrip("-").isdigit():
            user_id = int(identifier)
        else:
            chat = await context.bot.get_chat(identifier)
            user_id = chat.id
    except Exception as e:
        await _reply(update, f"❌ Could not find user: {e}")
        return

    async with AsyncSessionLocal() as session:
        removed = await remove_allowed_admin(session, user_id)

    if removed:
        await _reply(update, f"✅ User <code>{user_id}</code> removed from allowed admins.")
    else:
        await _reply(update, f"❌ User <code>{user_id}</code> was not in the allowed admin list.")


@owner_only
async def cmd_list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with AsyncSessionLocal() as session:
        admins = await list_allowed_admins(session)

    if not admins:
        await _reply(update, "📋 No allowed admins configured yet.")
        return

    lines = ["📋 <b>Allowed Admins</b>\n"]
    for a in admins:
        lines.append(
            f"• <code>{a.user_id}</code> — <b>{a.tier}</b> ({TIER_LABELS.get(a.tier, a.tier)})"
        )
    await _reply(update, "\n".join(lines))


async def owner_panel_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if not user or user.id != cfg.OWNER_ID:
        await query.answer("⛔ Owner only.", show_alert=True)
        return

    data = query.data

    if data == "oadmin:close":
        await query.delete_message()
        return

    elif data == "oadmin:list":
        async with AsyncSessionLocal() as session:
            admins = await list_allowed_admins(session)
        if not admins:
            text = "📋 No allowed admins yet."
        else:
            lines = ["📋 <b>Allowed Admins</b>\n"]
            for a in admins:
                lines.append(f"• <code>{a.user_id}</code> — <b>{a.tier}</b>")
            text = "\n".join(lines)

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Back", callback_data="oadmin:back")]
            ]),
        )

    elif data == "oadmin:add":
        await query.edit_message_text(
            "➕ <b>Add Allowed Admin</b>\n\n"
            "Send the command:\n"
            "<code>/addadmin @username full</code>\n\n"
            "Tiers:\n"
            "• <code>full</code> — Complete private panel\n"
            "• <code>limited</code> — Limited commands\n"
            "• <code>group_only</code> — Group use only\n"
            "• <code>readonly</code> — Help only",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Back", callback_data="oadmin:back")]
            ]),
        )

    elif data == "oadmin:remove":
        await query.edit_message_text(
            "➖ <b>Remove Allowed Admin</b>\n\n"
            "Send the command:\n"
            "<code>/removeadmin @username</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("« Back", callback_data="oadmin:back")]
            ]),
        )

    elif data == "oadmin:back":
        await query.edit_message_text(
            "👑 <b>Admin Access Panel</b>\n\n"
            "Manage which users have private-chat bot access.",
            parse_mode="HTML",
            reply_markup=admin_panel_menu(),
        )


def register(application) -> None:
    application.add_handler(CommandHandler("adminpanel",    cmd_admin_panel))
    application.add_handler(CommandHandler("addadmin",      cmd_add_admin))
    application.add_handler(CommandHandler("removeadmin",   cmd_remove_admin))
    application.add_handler(CommandHandler("listadmins",    cmd_list_admins))
    application.add_handler(
        CallbackQueryHandler(owner_panel_callback, pattern=r"^oadmin:")
    )
