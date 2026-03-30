"""handlers/settings.py — Per-group settings commands and inline menu."""

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

from database.engine import AsyncSessionLocal
from database.repository import get_group_settings, update_group_settings
from keyboards.menus import settings_menu, setting_back, toggle_button
from utils.decorators import group_admin_only, group_only
from utils.helpers import auto_delete
from utils.time_parser import parse_duration, seconds_to_human
from handlers.errors import handle_errors
import config as cfg


async def _auto(message: Message, text: str, delay: int = 5) -> None:
    msg = await message.reply(text)
    asyncio.create_task(auto_delete(msg, delay))
    asyncio.create_task(auto_delete(message, 3))


@handle_errors
@group_admin_only
@group_only
async def cmd_settings(client: Client, message: Message) -> None:
    chat = message.chat
    await message.reply(
        f"⚙️ <b>Settings for {chat.title}</b>\n\nSelect a category:",
        reply_markup=settings_menu(chat.id),
    )
    asyncio.create_task(auto_delete(message, 3))


@handle_errors
async def settings_callback(client: Client, callback_query: CallbackQuery) -> None:
    await callback_query.answer()
    data = callback_query.data

    if data == "cfg:close":
        await callback_query.message.delete()
        return

    parts = data.split(":")
    if len(parts) < 3:
        return

    chat_id = int(parts[1])
    section = parts[2]

    async with AsyncSessionLocal() as session:
        s = await get_group_settings(session, chat_id)

    if section == "main":
        await callback_query.edit_message_text(
            "⚙️ <b>Settings</b>\n\nSelect a category:",
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
        await callback_query.edit_message_text(text, reply_markup=kb)

    elif section == "antispam":
        kb = InlineKeyboardMarkup([
            [toggle_button("Anti-Spam", s.antispam_enabled, f"cfg:{chat_id}:toggle:antispam")],
            [toggle_button("Anti-Link", s.antilink_enabled, f"cfg:{chat_id}:toggle:antilink")],
            [toggle_button("Anti-Forward", s.antiforward_enabled, f"cfg:{chat_id}:toggle:antiforward")],
            [InlineKeyboardButton("« Back", callback_data=f"cfg:{chat_id}:main")],
        ])
        await callback_query.edit_message_text("🛡 <b>Anti-Spam Settings</b>", reply_markup=kb)

    elif section == "antilink":
        kb = InlineKeyboardMarkup([
            [toggle_button("Anti-Link", s.antilink_enabled, f"cfg:{chat_id}:toggle:antilink")],
            [InlineKeyboardButton("« Back", callback_data=f"cfg:{chat_id}:main")],
        ])
        await callback_query.edit_message_text("🔗 <b>Anti-Link Settings</b>", reply_markup=kb)

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
        await callback_query.edit_message_text(text, reply_markup=kb)

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
        await callback_query.edit_message_text(text, reply_markup=kb)

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
        await callback_query.edit_message_text(
            "🔒 <b>Content Locks</b>\n\nTap to toggle:",
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
        await callback_query.edit_message_text(text, reply_markup=kb)

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
        await callback_query.edit_message_text(text, reply_markup=kb)

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
            parent_map = {
                "welcome": "welcome", "antispam": "antispam",
                "antilink": "antispam", "antiforward": "antispam",
                "flood": "flood", "log_cleanup": "logging",
                "delete_join_msg": "autodelete", "delete_left_msg": "autodelete",
            }
            parent = parent_map.get(field, "main")
            callback_query.data = f"cfg:{chat_id}:{parent}"
            await settings_callback(client, callback_query)

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
        callback_query.data = f"cfg:{chat_id}:locks"
        await settings_callback(client, callback_query)


@handle_errors
@group_admin_only
@group_only
async def cmd_setrules(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    text = " ".join(args) if args else None
    if not text:
        await _auto(message, "❌ Usage: /setrules <your rules text>")
        return
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, message.chat.id, rules=text)
    await _auto(message, "✅ Group rules updated.")


@handle_errors
@group_admin_only
@group_only
async def cmd_rules(client: Client, message: Message) -> None:
    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, message.chat.id)
    text = settings.rules or "No rules have been set. Use /setrules to add them."
    msg = await message.reply(f"📜 <b>Group Rules</b>\n\n{text}")
    asyncio.create_task(auto_delete(message, 3))


@handle_errors
@group_admin_only
@group_only
async def cmd_setwelcome(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    text = " ".join(args) if args else None
    if not text:
        await _auto(message, "❌ Usage: /setwelcome <text>\nVariables: {mention} {name} {group}")
        return
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, message.chat.id, welcome_text=text)
    await _auto(message, "✅ Welcome message updated.")


@handle_errors
@group_admin_only
@group_only
async def cmd_setwarnlimit(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    if not args or not args[0].isdigit():
        await _auto(message, "❌ Usage: /setwarnlimit <number>")
        return
    val = max(1, int(args[0]))
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, message.chat.id, warn_limit=val)
    await _auto(message, f"✅ Warn limit set to <b>{val}</b>.")


@handle_errors
@group_admin_only
@group_only
async def cmd_setwarnaction(client: Client, message: Message) -> None:
    valid = ("mute", "kick", "ban")
    args = message.command[1:] if message.command else []
    if not args or args[0].lower() not in valid:
        await _auto(message, "❌ Usage: /setwarnaction mute|kick|ban")
        return
    val = args[0].lower()
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, message.chat.id, warn_action=val)
    await _auto(message, f"✅ Warn action set to <b>{val}</b>.")


@handle_errors
@group_admin_only
@group_only
async def cmd_setprefix(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    if not args:
        await _auto(message, "❌ Usage: /setprefix <prefix>  (e.g. . or !)")
        return
    prefix = args[0][:3]
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, message.chat.id, prefix=prefix)
    await _auto(message, f"✅ Command prefix set to <code>{prefix}</code>.")


@handle_errors
@group_admin_only
@group_only
async def cmd_setlogchannel(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    if not args:
        await _auto(message, "❌ Usage: /setlogchannel @channel or channel_id")
        return
    arg = args[0]
    try:
        if arg.lstrip("-").isdigit():
            channel_id = int(arg)
        else:
            chat = await client.get_chat(arg)
            channel_id = chat.id
        async with AsyncSessionLocal() as session:
            await update_group_settings(session, message.chat.id, log_channel_id=channel_id)
        await _auto(message, f"✅ Log channel set to <code>{channel_id}</code>.")
    except Exception as e:
        await _auto(message, f"❌ Could not resolve channel: {e}")


@handle_errors
@group_admin_only
@group_only
async def cmd_setcmddelay(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    if not args or not args[0].isdigit():
        await _auto(message, "❌ Usage: /setcmddelay <seconds>")
        return
    val = int(args[0])
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, message.chat.id, delete_cmd_delay=val)
    await _auto(message, f"✅ Command/bot message delete delay set to <b>{val}s</b>.")


@handle_errors
@group_admin_only
@group_only
async def cmd_setediteddelay(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    if not args or not args[0].isdigit():
        await _auto(message, "❌ Usage: /setediteddelay <seconds>  (0 = disabled)")
        return
    val = int(args[0])
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, message.chat.id, delete_edited_delay=val)
    status = f"<b>{val}s</b>" if val > 0 else "<b>disabled</b>"
    await _auto(message, f"✅ Edited message delete delay set to {status}.")


def register(app: Client) -> None:
    app.add_handler(MessageHandler(cmd_settings,      filters.command("settings")       & filters.group))
    app.add_handler(MessageHandler(cmd_rules,          filters.command("rules")          & filters.group))
    app.add_handler(MessageHandler(cmd_setrules,       filters.command("setrules")       & filters.group))
    app.add_handler(MessageHandler(cmd_setwelcome,     filters.command("setwelcome")     & filters.group))
    app.add_handler(MessageHandler(cmd_setwarnlimit,   filters.command("setwarnlimit")   & filters.group))
    app.add_handler(MessageHandler(cmd_setwarnaction,  filters.command("setwarnaction")  & filters.group))
    app.add_handler(MessageHandler(cmd_setprefix,      filters.command("setprefix")      & filters.group))
    app.add_handler(MessageHandler(cmd_setlogchannel,  filters.command("setlogchannel")  & filters.group))
    app.add_handler(MessageHandler(cmd_setcmddelay,    filters.command("setcmddelay")    & filters.group))
    app.add_handler(MessageHandler(cmd_setediteddelay, filters.command("setediteddelay") & filters.group))
    app.add_handler(CallbackQueryHandler(settings_callback, filters.regex(r"^cfg:")))
