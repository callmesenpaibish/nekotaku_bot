"""handlers/settings.py — Per-group settings commands and inline menu."""

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.errors import RPCError

from database.engine import AsyncSessionLocal
from database.repository import get_group_settings, update_group_settings
from keyboards.menus import settings_menu, setting_back, toggle_button
from utils.decorators import group_admin_only, group_only
from utils.helpers import auto_delete
from utils.time_parser import seconds_to_human
from handlers.errors import handle_errors
import config as cfg


async def _auto(message: Message, text: str, delay: int = 5) -> None:
    msg = await message.reply(text)
    asyncio.create_task(auto_delete(msg, delay))
    asyncio.create_task(auto_delete(message, 3))


# ── Section renderers (called by both direct nav and toggle callbacks) ─────────

async def _render_main(client: Client, cq: CallbackQuery, chat_id: int) -> None:
    chat = cq.message.chat
    title = chat.title if chat else "group"
    await cq.edit_message_text(
        f"⚙️ <b>Settings for {title}</b>\n\nSelect a category:",
        reply_markup=settings_menu(chat_id),
    )


async def _render_welcome(client: Client, cq: CallbackQuery, chat_id: int) -> None:
    async with AsyncSessionLocal() as session:
        s = await get_group_settings(session, chat_id)

    has_media = bool(s.welcome_msg_id)
    text_preview = (s.welcome_text or cfg.DEFAULT_WELCOME)[:120]
    kb = InlineKeyboardMarkup([
        [toggle_button("Welcome Messages", s.welcome_enabled, f"cfg:{chat_id}:toggle:welcome_enabled")],
        [InlineKeyboardButton("« Back", callback_data=f"cfg:{chat_id}:main")],
    ])
    body = (
        f"👋 <b>Welcome Settings</b>\n\n"
        f"Status: {'✅ Enabled' if s.welcome_enabled else '❌ Disabled'}\n"
        f"Template: {'📎 Media message set' if has_media else '📝 Text only'}\n\n"
        f"<b>Current text:</b>\n<code>{text_preview}</code>\n\n"
        "To change: reply to any message (with or without media) and use:\n"
        "<code>/setwelcome [optional caption]</code>\n\n"
        "Variables: <code>{mention}</code> <code>{name}</code> <code>{group}</code>"
    )
    await cq.edit_message_text(body, reply_markup=kb)


async def _render_antispam(client: Client, cq: CallbackQuery, chat_id: int) -> None:
    async with AsyncSessionLocal() as session:
        s = await get_group_settings(session, chat_id)
    kb = InlineKeyboardMarkup([
        [toggle_button("Anti-Spam",    s.antispam_enabled,    f"cfg:{chat_id}:toggle:antispam_enabled")],
        [toggle_button("Anti-Link",    s.antilink_enabled,    f"cfg:{chat_id}:toggle:antilink_enabled")],
        [toggle_button("Anti-Forward", s.antiforward_enabled, f"cfg:{chat_id}:toggle:antiforward_enabled")],
        [InlineKeyboardButton("« Back", callback_data=f"cfg:{chat_id}:main")],
    ])
    await cq.edit_message_text("🛡 <b>Anti-Spam Settings</b>", reply_markup=kb)


async def _render_flood(client: Client, cq: CallbackQuery, chat_id: int) -> None:
    async with AsyncSessionLocal() as session:
        s = await get_group_settings(session, chat_id)
    kb = InlineKeyboardMarkup([
        [toggle_button("Anti-Flood", s.flood_enabled, f"cfg:{chat_id}:toggle:flood_enabled")],
        [InlineKeyboardButton("« Back", callback_data=f"cfg:{chat_id}:main")],
    ])
    text = (
        f"🌊 <b>Flood Settings</b>\n\n"
        f"Rate: <code>{s.flood_rate}</code> msgs / <code>{s.flood_window}s</code> window\n"
        f"Mute duration: <code>{seconds_to_human(s.spam_mute_duration)}</code>\n\n"
        "Change with: <code>/floodrate &lt;n&gt;</code> · <code>/floodwindow &lt;s&gt;</code>"
    )
    await cq.edit_message_text(text, reply_markup=kb)


async def _render_warnlimit(client: Client, cq: CallbackQuery, chat_id: int) -> None:
    async with AsyncSessionLocal() as session:
        s = await get_group_settings(session, chat_id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("« Back", callback_data=f"cfg:{chat_id}:main")],
    ])
    text = (
        f"⚠️ <b>Warn System</b>\n\n"
        f"Limit: <code>{s.warn_limit}</code> warns\n"
        f"Action: <code>{s.warn_action}</code>\n\n"
        "Change with:\n"
        "<code>/setwarnlimit &lt;n&gt;</code>\n"
        "<code>/setwarnaction mute|kick|ban</code>"
    )
    await cq.edit_message_text(text, reply_markup=kb)


async def _render_locks(client: Client, cq: CallbackQuery, chat_id: int) -> None:
    from handlers.locks import VALID_LOCKS
    async with AsyncSessionLocal() as session:
        s = await get_group_settings(session, chat_id)
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
    await cq.edit_message_text(
        "🔒 <b>Content Locks</b>\n\nTap to toggle. Permission-based locks prevent sending at the Telegram level.\n<i>Note: image/video/audio/document share one permission slot.</i>",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def _render_logging(client: Client, cq: CallbackQuery, chat_id: int) -> None:
    async with AsyncSessionLocal() as session:
        s = await get_group_settings(session, chat_id)
    kb = InlineKeyboardMarkup([
        [toggle_button("Log Cleanup Actions", s.log_cleanup, f"cfg:{chat_id}:toggle:log_cleanup")],
        [InlineKeyboardButton("« Back", callback_data=f"cfg:{chat_id}:main")],
    ])
    dest = f"<code>{s.log_channel_id}</code>" if s.log_channel_id else "Not set"
    await cq.edit_message_text(
        f"📋 <b>Logging Settings</b>\n\nLog destination: {dest}\n\n"
        "Change with: <code>/setlogchannel @channel</code>",
        reply_markup=kb,
    )


async def _render_autodelete(client: Client, cq: CallbackQuery, chat_id: int) -> None:
    async with AsyncSessionLocal() as session:
        s = await get_group_settings(session, chat_id)
    kb = InlineKeyboardMarkup([
        [toggle_button("Delete Join Messages", s.delete_join_msg,  f"cfg:{chat_id}:toggle:delete_join_msg")],
        [toggle_button("Delete Left Messages", s.delete_left_msg,  f"cfg:{chat_id}:toggle:delete_left_msg")],
        [InlineKeyboardButton("« Back", callback_data=f"cfg:{chat_id}:main")],
    ])
    text = (
        f"🗑 <b>Auto-Delete Settings</b>\n\n"
        f"Command msg delay: <code>{s.delete_cmd_delay}s</code>\n\n"
        "Change with: <code>/setcmddelay &lt;seconds&gt;</code>"
    )
    await cq.edit_message_text(text, reply_markup=kb)


async def _render_editedmsg(client: Client, cq: CallbackQuery, chat_id: int) -> None:
    async with AsyncSessionLocal() as session:
        s = await get_group_settings(session, chat_id)
    delay_str = f"after <code>{s.delete_edited_delay}s</code>" if s.delete_edited_delay > 0 else "immediately"
    kb = InlineKeyboardMarkup([
        [toggle_button("Delete Edited Messages", s.delete_edited_msg, f"cfg:{chat_id}:toggle:delete_edited_msg")],
        [InlineKeyboardButton("« Back", callback_data=f"cfg:{chat_id}:main")],
    ])
    text = (
        f"✏️ <b>Edited Message Settings</b>\n\n"
        f"Delete edited messages: {'✅ Yes' if s.delete_edited_msg else '❌ No'}\n"
        f"Delay: {delay_str}\n\n"
        "Change delay: <code>/setediteddelay &lt;seconds&gt;</code>\n"
        "<i>Set to 0 to delete immediately when enabled.</i>"
    )
    await cq.edit_message_text(text, reply_markup=kb)


# Section map
_SECTION_RENDERERS = {
    "main":       _render_main,
    "welcome":    _render_welcome,
    "antispam":   _render_antispam,
    "antilink":   _render_antispam,
    "flood":      _render_flood,
    "warnlimit":  _render_warnlimit,
    "locks":      _render_locks,
    "logging":    _render_logging,
    "autodelete": _render_autodelete,
    "editedmsg":  _render_editedmsg,
}

# Bool field → parent section
_TOGGLE_PARENT = {
    "welcome_enabled":    "welcome",
    "antispam_enabled":   "antispam",
    "antilink_enabled":   "antispam",
    "antiforward_enabled":"antispam",
    "flood_enabled":      "flood",
    "log_cleanup":        "logging",
    "delete_join_msg":    "autodelete",
    "delete_left_msg":    "autodelete",
    "delete_edited_msg":  "editedmsg",
}


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
    # Only the group admin who opened the panel (or any admin) may interact with it
    user = callback_query.from_user
    chat = callback_query.message.chat
    if not user or not chat:
        await callback_query.answer("⛔ Cannot verify identity.", show_alert=True)
        return

    from utils.helpers import is_admin
    from config import OWNER_ID
    if user.id != OWNER_ID and not await is_admin(client, chat.id, user.id):
        await callback_query.answer("⛔ Only group admins can change settings.", show_alert=True)
        return

    await callback_query.answer()
    data = callback_query.data

    if data == "cfg:close":
        await callback_query.message.delete()
        return

    parts = data.split(":")
    if len(parts) < 3:
        return

    chat_id = int(parts[1])
    section = ":".join(parts[2:])  # handles sub-sections like "toggle:welcome_enabled"

    # ── Section navigation ─────────────────────────────────────────────────────
    renderer = _SECTION_RENDERERS.get(section)
    if renderer:
        await renderer(client, callback_query, chat_id)
        return

    # ── Bool toggle ────────────────────────────────────────────────────────────
    if section.startswith("toggle:"):
        field = section[len("toggle:"):]
        if field in _TOGGLE_PARENT:
            async with AsyncSessionLocal() as session:
                s = await get_group_settings(session, chat_id)
                new_val = not getattr(s, field)
                await update_group_settings(session, chat_id, **{field: new_val})
            parent = _TOGGLE_PARENT[field]
            renderer = _SECTION_RENDERERS.get(parent, _render_main)
            await renderer(client, callback_query, chat_id)
        return

    # ── Lock toggle ────────────────────────────────────────────────────────────
    if section.startswith("togglelock:"):
        lt = section[len("togglelock:"):]
        from handlers.locks import VALID_LOCKS, PERMISSION_LOCKS
        if lt not in VALID_LOCKS:
            return
        async with AsyncSessionLocal() as session:
            s = await get_group_settings(session, chat_id)
            locked = set((s.locked_types or "").split(","))
            locked.discard("")
            if lt in locked:
                locked.discard(lt)
            else:
                locked.add(lt)
            await update_group_settings(session, chat_id, locked_types=",".join(locked))

        from services.moderation_service import apply_group_lock
        if lt in PERMISSION_LOCKS:
            await apply_group_lock(client, chat_id, locked & PERMISSION_LOCKS)

        await _render_locks(client, callback_query, chat_id)
        return


# ── Text commands ──────────────────────────────────────────────────────────────

@handle_errors
@group_admin_only
@group_only
async def cmd_setrules(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    text = " ".join(args).strip() if args else None
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
    await message.reply(f"📜 <b>Group Rules</b>\n\n{text}")
    asyncio.create_task(auto_delete(message, 3))


@handle_errors
@group_admin_only
@group_only
async def cmd_setwelcome(client: Client, message: Message) -> None:
    """
    Usage:
      - Reply to any message (with or without media): /setwelcome [optional text]
      - Or: /setwelcome <text>  (text only, no media)
    Supports {mention}, {name}, {group} variables in text.
    """
    reply = message.reply_to_message
    args = message.command[1:] if message.command else []
    caption = " ".join(args).strip() if args else None

    if reply:
        # Store the replied message as the welcome template
        async with AsyncSessionLocal() as session:
            await update_group_settings(
                session, message.chat.id,
                welcome_msg_id=reply.id,
                welcome_msg_chat_id=message.chat.id,
                welcome_text=caption or None,
            )
        media_type = "media message" if (reply.photo or reply.video or reply.animation or reply.document or reply.sticker) else "text message"
        await _auto(
            message,
            f"✅ Welcome template set to the replied {media_type}."
            + (f"\nCaption: <code>{caption}</code>" if caption else ""),
        )
    elif caption:
        async with AsyncSessionLocal() as session:
            await update_group_settings(
                session, message.chat.id,
                welcome_text=caption,
                welcome_msg_id=None,
                welcome_msg_chat_id=None,
            )
        await _auto(message, f"✅ Welcome text updated:\n<code>{caption[:200]}</code>")
    else:
        await _auto(
            message,
            "❌ Usage:\n"
            "• Reply to a message + /setwelcome [caption]\n"
            "• /setwelcome &lt;text&gt;\n\n"
            "Variables: <code>{mention}</code> <code>{name}</code> <code>{group}</code>"
        )


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
    except RPCError as e:
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
    await _auto(message, f"✅ Command message delete delay set to <b>{val}s</b>.")


@handle_errors
@group_admin_only
@group_only
async def cmd_setediteddelay(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    if not args or not args[0].isdigit():
        await _auto(message, "❌ Usage: /setediteddelay <seconds>  (0 = immediate)")
        return
    val = int(args[0])
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, message.chat.id, delete_edited_delay=val)
    status = f"<b>{val}s</b>" if val > 0 else "<b>immediate</b>"
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
