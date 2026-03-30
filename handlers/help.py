"""handlers/help.py — Private chat help panel with role-based content."""

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

import config as cfg
from keyboards.menus import help_main_menu, help_back_button
from middleware.permissions import resolve_role, Role, can_use_private_panel
from handlers.errors import handle_errors

HELP_SECTIONS = {
    "mod": (
        "🔨 <b>Moderation Commands</b>\n\n"
        "<code>.mute @user [reason]</code> — Mute a user indefinitely\n"
        "<code>.tmute @user 10m [reason]</code> — Timed mute (s/m/h/d)\n"
        "<code>.unmute @user</code> — Remove mute\n"
        "<code>.kick @user [reason]</code> — Kick user from group\n"
        "<code>.ban @user [reason]</code> — Ban user\n"
        "<code>.tban @user 2h [reason]</code> — Timed ban\n"
        "<code>.unban @user</code> — Remove ban\n"
        "<code>.del</code> (reply) — Delete a message\n\n"
        "All commands also work by replying to the target message."
    ),
    "spam": (
        "🛡 <b>Anti-Spam Commands</b>\n\n"
        "<code>/antispam on|off</code> — Toggle anti-spam\n"
        "<code>/antilink on|off</code> — Toggle link blocking\n"
        "<code>/antiflood on|off</code> — Toggle flood protection\n"
        "<code>/floodrate 5</code> — Set max messages per window\n"
        "<code>/floodwindow 5</code> — Set flood window (seconds)\n\n"
        "When triggered, the bot auto-mutes and logs the action."
    ),
    "locks": (
        "🔒 <b>Lock / Unlock Commands</b>\n\n"
        "<code>/lock link</code> — Block links from non-admins\n"
        "<code>/lock sticker</code> — Block stickers\n"
        "<code>/lock image</code> — Block images\n"
        "<code>/lock video</code> — Block videos\n"
        "<code>/lock forward</code> — Block forwarded messages\n"
        "<code>/lock audio</code> — Block audio files\n"
        "<code>/lock document</code> — Block documents\n"
        "<code>/unlock &lt;type&gt;</code> — Remove a lock\n"
        "<code>/locks</code> — View current locks"
    ),
    "warn": (
        "⚠️ <b>Warning System</b>\n\n"
        "<code>.warn @user [reason]</code> — Add a warning\n"
        "<code>.dwarn @user [reason]</code> — Warn + delete message\n"
        "<code>.unwarn @user</code> — Remove one warning\n"
        "<code>.resetwarn @user</code> — Reset all warnings\n"
        "<code>.warns @user</code> — View user's warnings\n\n"
        "Default limit: 3 warns → auto-mute.\n"
        "Change with: <code>/setwarnlimit 3</code>\n"
        "Change action with: <code>/setwarnaction mute|kick|ban</code>"
    ),
    "settings": (
        "⚙️ <b>Group Settings</b>\n\n"
        "<code>/settings</code> — Open interactive settings menu\n"
        "<code>/setrules &lt;text&gt;</code> — Set group rules\n"
        "<code>/setwelcome &lt;text&gt;</code> — Set welcome message\n"
        "  Variables: <code>{mention}</code>, <code>{name}</code>, <code>{group}</code>\n"
        "<code>/setprefix .</code> — Change command prefix\n"
        "<code>/setlogchannel @channel</code> — Set log destination\n\n"
        "All settings are per-group and persist across restarts."
    ),
    "admin": (
        "👮 <b>Admin Tools</b>\n\n"
        "<code>/promote @user</code> — Promote user to admin\n"
        "<code>/demote @user</code> — Demote admin\n"
        "<code>/pin [silent]</code> (reply) — Pin a message\n"
        "<code>/unpin</code> — Unpin pinned message\n"
        "<code>/rules</code> — Show group rules\n"
        "<code>/stats @user</code> — View user infraction history\n"
        "<code>/adminlist</code> — List all group admins"
    ),
    "owner": (
        "👑 <b>Owner Tools</b>\n\n"
        "<code>/addadmin @user full|limited|group_only|readonly</code>\n"
        "  — Grant private panel access to an admin\n"
        "<code>/removeadmin @user</code> — Revoke access\n"
        "<code>/listadmins</code> — Show all allowed admins\n"
        "<code>/adminpanel</code> — Open the admin management panel\n\n"
        "<b>Tiers:</b>\n"
        "• <code>full</code> — Full private panel\n"
        "• <code>limited</code> — Limited private access\n"
        "• <code>group_only</code> — Group commands only\n"
        "• <code>readonly</code> — Help only"
    ),
}


@handle_errors
async def start_handler(client: Client, message: Message) -> None:
    user = message.from_user
    if not user:
        return

    role = await resolve_role(client, user.id)

    if can_use_private_panel(role):
        is_owner = (user.id == cfg.OWNER_ID)
        text = (
            f"👑 Welcome, <b>{user.first_name}</b>!\n\n"
            "I'm a full-featured Telegram group moderation bot.\n"
            "Choose a category below to view available commands."
        )
        await message.reply(text, reply_markup=help_main_menu(is_owner=is_owner))
    elif role >= Role.LIMITED_ADMIN:
        await message.reply(
            f"👋 Hi {user.first_name}!\n"
            "You have limited access. Use /help to see your available commands."
        )
    else:
        await message.reply(
            "🤖 I am a moderation bot for a specific group.\n"
            "Add me to your group and make me an admin to get started."
        )


@handle_errors
async def help_callback_handler(client: Client, callback_query: CallbackQuery) -> None:
    await callback_query.answer()
    data = callback_query.data
    user = callback_query.from_user

    if data == "help:main":
        is_owner = (user.id == cfg.OWNER_ID)
        await callback_query.edit_message_text(
            "📖 <b>Help Menu</b>\n\nChoose a category:",
            reply_markup=help_main_menu(is_owner=is_owner),
        )
        return

    section = data.split(":")[-1]

    if section == "owner" and user.id != cfg.OWNER_ID:
        await callback_query.answer("⛔ Owner only.", show_alert=True)
        return

    text = HELP_SECTIONS.get(section)
    if not text:
        await callback_query.answer("Unknown section.", show_alert=True)
        return

    await callback_query.edit_message_text(text, reply_markup=help_back_button())


def register(app: Client) -> None:
    app.add_handler(MessageHandler(start_handler, filters.command("start") & filters.private))
    app.add_handler(MessageHandler(start_handler, filters.command("help") & filters.private))
    app.add_handler(CallbackQueryHandler(help_callback_handler, filters.regex(r"^help:")))
