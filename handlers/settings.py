"""handlers/settings.py — Per-group settings commands and inline menu."""

import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from database.engine import AsyncSessionLocal
from database.repository import get_group_settings, update_group_settings
from keyboards.menus import settings_menu, setting_back, toggle_button
from utils.decorators import group_admin_only, group_only
from utils.helpers import auto_delete
from utils.time_parser import parse_duration, seconds_to_human
import config as cfg


async def _auto(update: Update, text: str, delay: int = 5) -> None:
    msg = await update.effective_message.reply_text(text, parse_mode="HTML")
    asyncio.create_task(auto_delete(msg, delay))
    asyncio.create_task(auto_delete(update.effective_message, 3))


# ── /settings — main menu ────────────────────────────────────────────────────

@group_admin_only
@group_only
async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    await update.effective_message.reply_text(
        f"⚙️ <b>Settings for {chat.title}</b>\n\nSelect a category:",
        parse_mode="HTML",
        reply_markup=settings_menu(chat.id),
    )
    asyncio.create_task(auto_delete(update.effective_message, 3))


# ── Callback router ───────────────────────────────────────────────────────────

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data  # cfg:<chat_id>:<section> or cfg:close

    if data == "cfg:close":
        await query.delete_message()
        return

    parts = data.split(":")
    if len(parts) < 3:
        return

    chat_id = int(parts[1])
    section = parts[2]

    async with AsyncSessionLocal() as session:
        s = await get_group_settings(session, chat_id)

    if section == "main":
        await query.edit_message_text(
            "⚙️ <b>Settings</b>\n\nSelect a category:",
            parse_mode="HTML",
            reply_markup=settings_menu(chat_id),
        )

    elif section == "welcome":
        kb = InlineKeyboardMarkup([
            [toggle_button("Welcome Messages", s.welcome_enabled, f"cfg:{chat_id}:toggle:welcome")],
            [InlineKeyboardButton("✏️ Edit Welcome Text", callback_data=f"cfg:{chat_id}:setwelcome")],
            [InlineKeyboardButton("« Back", callback_data=f"cfg:{chat_id}:main")],
        ])
        text = (
            f"👋 <b>Welcome Settings</b>\n\n"
            f"Status: {'✅ Enabled' if s.welcome_enabled else '❌ Disabled'}\n\n"
            f"<b>Current text:</b>\n<code>{s.welcome_text or cfg.DEFAULT_WELCOME}</code>\n\n"
            "Variables: <code>{mention}</code>, <code>{name}</code>, <code>{group}</code>"
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)

    elif section == "antispam":
        kb = InlineKeyboardMarkup([
            [toggle_button("Anti-Spam", s.antispam_enabled, f"cfg:{chat_id}:toggle:antispam")],
            [toggle_button("Anti-Link", s.antilink_enabled, f"cfg:{chat_id}:toggle:antilink")],
            [toggle_button("Anti-Forward", s.antiforward_enabled, f"cfg:{chat_id}:toggle:antiforward")],
            [InlineKeyboardButton("« Back", callback_data=f"cfg:{chat_id}:main")],
        ])
        await query.edit_message_text(
            "🛡 <b>Anti-Spam Settings</b>",
            parse_mode="HTML", reply_markup=kb,
        )

    elif section == "flood":
        kb = InlineKeyboardMarkup([
            [toggle_button("Anti-Flood", s.flood_enabled, f"cfg:{chat_id}:toggle:flood")],
            [InlineKeyboardButton("« Back", callback_data=f"cfg:{chat_id}:main")],
        ])
        text = (
            f"🌊 <b>Flood Settings</b>\n\n"
            f"Rate: <code>{s.flood_rate}</code> msgs / <code>{s.flood_window}</code>s\n"
            f"Mute duration: <code>{seconds_to_human(s.spam_mute_duration)}</code>\n\n"
            "Change with: /floodrate, /floodwindow"
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)

    elif section == "warnlimit":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("« Back", callback_data=f"cfg:{chat_id}:main")],
        ])
        text = (
            f"⚠️ <b>Warn System</b>\n\n"
            f"Limit: <code>{s.warn_limit}</code> warns\n"
            f"Action: <code>{s.warn_action}</code>\n\n"
            "Change with:\n"
            "<code>/setwarnlimit 3</code>\n"
            "<code>/setwarnaction mute|kick|ban</code>"
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)

    elif section == "locks":
        from handlers.locks import VALID_LOCKS
        locked = set((s.locked_types or "").split(","))
        locked.discard("")
        buttons = []
        row = []
        for lt in sorted(VALID_LOCKS):
            icon = "🔒" if lt in locked else "🔓"
            row.append(InlineKeyboardButton(f"{icon} {lt}", callback_data=f"cfg:{chat_id}:togglelock:{lt}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([InlineKeyboardButton("« Back", callback_data=f"cfg:{chat_id}:main")])
        await query.edit_message_text(
            "🔒 <b>Content Locks</b>\n\nTap to toggle:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    elif section == "logging":
        kb = InlineKeyboardMarkup([
            [toggle_button("Log Cleanup Actions", s.log_cleanup, f"cfg:{chat_id}:toggle:log_cleanup")],
            [InlineKeyboardButton("« Back", callback_data=f"cfg:{chat_id}:main")],
        ])
        dest = f"<code>{s.log_channel_id}</code>" if s.log_channel_id else "Not set"
        text = (
            f"📋 <b>Logging Settings</b>\n\n"
            f"Log destination: {dest}\n\n"
            "Change with: <code>/setlogchannel @channel</code>"
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)

    elif section == "autodelete":
        kb = InlineKeyboardMarkup([
            [toggle_button("Delete Join Messages", s.delete_join_msg, f"cfg:{chat_id}:toggle:delete_join_msg")],
            [toggle_button("Delete Left Messages", s.delete_left_msg, f"cfg:{chat_id}:toggle:delete_left_msg")],
            [InlineKeyboardButton("« Back", callback_data=f"cfg:{chat_id}:main")],
        ])
        text = (
            f"🗑 <b>Auto-Delete Settings</b>\n\n"
            f"Command/bot msg delay: <code>{s.delete_cmd_delay}s</code>\n"
            f"Edited msg delay: <code>{s.delete_edited_delay}s</code>\n\n"
            "Change with: <code>/setcmddelay &lt;seconds&gt;</code>\n"
            "<code>/setediteddelay &lt;seconds&gt;</code>"
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)

    elif section.startswith("toggle:"):
        field = section.split(":", 1)[1]
        _bool_fields = {
            "welcome": "welcome_enabled",
            "antispam": "antispam_enabled",
            "antilink": "antilink_enabled",
            "antiforward": "antiforward_enabled",
            "flood": "flood_enabled",
            "log_cleanup": "log_cleanup",
            "delete_join_msg": "delete_join_msg",
            "delete_left_msg": "delete_left_msg",
        }
        db_field = _bool_fields.get(field)
        if db_field:
            async with AsyncSessionLocal() as session:
                settings = await get_group_settings(session, chat_id)
                new_val = not getattr(settings, db_field)
                await update_group_settings(session, chat_id, **{db_field: new_val})
            # Re-open the parent section
            parent_map = {
                "welcome": "welcome", "antispam": "antispam",
                "antilink": "antispam", "antiforward": "antispam",
                "flood": "flood", "log_cleanup": "logging",
                "delete_join_msg": "autodelete", "delete_left_msg": "autodelete",
            }
            parent = parent_map.get(field, "main")
            # Fake the data and re-call
            query.data = f"cfg:{chat_id}:{parent}"
            await settings_callback(update, context)

    elif section.startswith("togglelock:"):
        lt = section.split(":", 1)[1]
        async with AsyncSessionLocal() as session:
            settings = await get_group_settings(session, chat_id)
            locked = set((settings.locked_types or "").split(","))
            locked.discard("")
            if lt in locked:
                locked.discard(lt)
            else:
                locked.add(lt)
            await update_group_settings(session, chat_id, locked_types=",".join(locked))
        query.data = f"cfg:{chat_id}:locks"
        await settings_callback(update, context)


# ── Text-based settings commands ─────────────────────────────────────────────

@group_admin_only
@group_only
async def cmd_setrules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args) if context.args else None
    if not text:
        await _auto(update, "❌ Usage: /setrules <your rules text>")
        return
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, update.effective_chat.id, rules=text)
    await _auto(update, "✅ Group rules updated.")


@group_admin_only
@group_only
async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, update.effective_chat.id)
    text = settings.rules or "No rules have been set. Use /setrules to add them."
    msg = await update.effective_message.reply_text(
        f"📜 <b>Group Rules</b>\n\n{text}", parse_mode="HTML"
    )
    asyncio.create_task(auto_delete(update.effective_message, 3))


@group_admin_only
@group_only
async def cmd_setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args) if context.args else None
    if not text:
        await _auto(update, "❌ Usage: /setwelcome <text>\nVariables: {mention} {name} {group}")
        return
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, update.effective_chat.id, welcome_text=text)
    await _auto(update, "✅ Welcome message updated.")


@group_admin_only
@group_only
async def cmd_setwarnlimit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or not context.args[0].isdigit():
        await _auto(update, "❌ Usage: /setwarnlimit <number>")
        return
    val = max(1, int(context.args[0]))
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, update.effective_chat.id, warn_limit=val)
    await _auto(update, f"✅ Warn limit set to <b>{val}</b>.")


@group_admin_only
@group_only
async def cmd_setwarnaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    valid = ("mute", "kick", "ban")
    if not context.args or context.args[0].lower() not in valid:
        await _auto(update, "❌ Usage: /setwarnaction mute|kick|ban")
        return
    val = context.args[0].lower()
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, update.effective_chat.id, warn_action=val)
    await _auto(update, f"✅ Warn action set to <b>{val}</b>.")


@group_admin_only
@group_only
async def cmd_setprefix(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await _auto(update, "❌ Usage: /setprefix <prefix>  (e.g. . or !)")
        return
    prefix = context.args[0][:3]
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, update.effective_chat.id, prefix=prefix)
    await _auto(update, f"✅ Command prefix set to <code>{prefix}</code>.")


@group_admin_only
@group_only
async def cmd_setlogchannel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await _auto(update, "❌ Usage: /setlogchannel @channel or channel_id")
        return
    arg = context.args[0]
    try:
        if arg.lstrip("-").isdigit():
            channel_id = int(arg)
        else:
            chat = await context.bot.get_chat(arg)
            channel_id = chat.id
        async with AsyncSessionLocal() as session:
            await update_group_settings(session, update.effective_chat.id, log_channel_id=channel_id)
        await _auto(update, f"✅ Log channel set to <code>{channel_id}</code>.")
    except Exception as e:
        await _auto(update, f"❌ Could not resolve channel: {e}")


@group_admin_only
@group_only
async def cmd_setcmddelay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or not context.args[0].isdigit():
        await _auto(update, "❌ Usage: /setcmddelay <seconds>")
        return
    val = int(context.args[0])
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, update.effective_chat.id, delete_cmd_delay=val)
    await _auto(update, f"✅ Command/bot/join/left message delete delay set to <b>{val}s</b>.")


@group_admin_only
@group_only
async def cmd_setediteddelay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or not context.args[0].isdigit():
        await _auto(update, "❌ Usage: /setediteddelay <seconds>  (0 = disabled)")
        return
    val = int(context.args[0])
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, update.effective_chat.id, delete_edited_delay=val)
    status = f"<b>{val}s</b>" if val > 0 else "<b>disabled</b>"
    await _auto(update, f"✅ Edited message delete delay set to {status}.")


def register(application) -> None:
    application.add_handler(CommandHandler("settings",       cmd_settings))
    application.add_handler(CommandHandler("rules",          cmd_rules))
    application.add_handler(CommandHandler("setrules",       cmd_setrules))
    application.add_handler(CommandHandler("setwelcome",     cmd_setwelcome))
    application.add_handler(CommandHandler("setwarnlimit",   cmd_setwarnlimit))
    application.add_handler(CommandHandler("setwarnaction",  cmd_setwarnaction))
    application.add_handler(CommandHandler("setprefix",      cmd_setprefix))
    application.add_handler(CommandHandler("setlogchannel",  cmd_setlogchannel))
    application.add_handler(CommandHandler("setcmddelay",    cmd_setcmddelay))
    application.add_handler(CommandHandler("setediteddelay", cmd_setediteddelay))
    application.add_handler(
        CallbackQueryHandler(settings_callback, pattern=r"^cfg:")
    )
