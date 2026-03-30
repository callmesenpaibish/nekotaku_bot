"""handlers/antispam.py — Anti-spam, anti-link, anti-flood, anti-forward."""

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler, EditedMessageHandler

from database.engine import AsyncSessionLocal
from database.repository import get_group_settings, update_group_settings
from services.spam_service import check_flood, reset_flood, contains_link
from services.moderation_service import mute_user
from services.log_service import send_log
from utils.helpers import safe_delete, auto_delete, is_admin, mention_html
from utils.decorators import group_admin_only, group_only
from handlers.errors import handle_errors


@handle_errors
async def _handle_incoming(client: Client, message: Message) -> None:
    user = message.from_user
    chat = message.chat

    if not user or not chat:
        return
    if user.is_bot:
        return
    if await is_admin(client, chat.id, user.id):
        return

    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat.id)

    # ── Flood check ───────────────────────────────────────────────────────────
    if settings.flood_enabled:
        flooded = check_flood(
            chat.id, user.id,
            rate=settings.flood_rate,
            window=settings.flood_window,
        )
        if flooded:
            reset_flood(chat.id, user.id)
            await safe_delete(message)
            duration = settings.spam_mute_duration
            ok = await mute_user(
                client, chat.id, user,
                reason="Flood protection triggered",
                duration=duration,
                auto=True,
            )
            if ok:
                notif = await client.send_message(
                    chat_id=chat.id,
                    text=(
                        f"🚫 {mention_html(user)} muted for flooding.\n"
                        f"Duration: {duration // 60}m"
                    ),
                )
                asyncio.create_task(auto_delete(notif, settings.delete_cmd_delay))
            return

    # ── Anti-link check ───────────────────────────────────────────────────────
    text = message.text or message.caption or ""
    if settings.antilink_enabled and text and contains_link(text):
        await safe_delete(message)
        notif = await client.send_message(
            chat_id=chat.id,
            text=f"🔗 {mention_html(user)}, links are not allowed here.",
        )
        asyncio.create_task(auto_delete(notif, settings.delete_cmd_delay))
        await send_log(
            client, chat.id, "antilink",
            target_user_id=user.id,
            target_username=user.username,
            reason="Link detected and deleted",
            auto=True,
        )
        return

    # ── Anti-forward check (can't be done via Telegram permissions) ───────────
    is_forward = bool(
        message.forward_from
        or message.forward_from_chat
        or message.forward_sender_name
    )
    if settings.antiforward_enabled and is_forward:
        await safe_delete(message)
        notif = await client.send_message(
            chat_id=chat.id,
            text=f"📤 {mention_html(user)}, forwarded messages are not allowed.",
        )
        asyncio.create_task(auto_delete(notif, settings.delete_cmd_delay))
        return

    # ── Forward lock (from locks system) — still needs message-level check ────
    locked = set((settings.locked_types or "").split(","))
    locked.discard("")
    if "forward" in locked and is_forward:
        await safe_delete(message)
        notif = await client.send_message(
            chat_id=chat.id,
            text=f"🔒 {mention_html(user)}, forwarded messages are locked.",
        )
        asyncio.create_task(auto_delete(notif, settings.delete_cmd_delay))
        return


@handle_errors
async def _handle_edited(client: Client, message: Message) -> None:
    chat = message.chat
    if not chat:
        return

    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat.id)

    if not settings.delete_edited_msg:
        return

    delay = settings.delete_edited_delay
    if delay <= 0:
        await safe_delete(message)
        return

    asyncio.create_task(auto_delete(message, delay))


@handle_errors
@group_admin_only
@group_only
async def cmd_antispam(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    if not args or args[0] not in ("on", "off"):
        await message.reply("Usage: /antispam on|off")
        return
    val = args[0] == "on"
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, message.chat.id, antispam_enabled=val)
    msg = await message.reply(f"🛡 Anti-spam: {'✅ enabled' if val else '❌ disabled'}")
    asyncio.create_task(auto_delete(msg, 5))
    asyncio.create_task(auto_delete(message, 3))


@handle_errors
@group_admin_only
@group_only
async def cmd_antilink(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    if not args or args[0] not in ("on", "off"):
        await message.reply("Usage: /antilink on|off")
        return
    val = args[0] == "on"
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, message.chat.id, antilink_enabled=val)
    msg = await message.reply(f"🔗 Anti-link: {'✅ enabled' if val else '❌ disabled'}")
    asyncio.create_task(auto_delete(msg, 5))
    asyncio.create_task(auto_delete(message, 3))


@handle_errors
@group_admin_only
@group_only
async def cmd_antiflood(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    if not args or args[0] not in ("on", "off"):
        await message.reply("Usage: /antiflood on|off")
        return
    val = args[0] == "on"
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, message.chat.id, flood_enabled=val)
    msg = await message.reply(f"🌊 Anti-flood: {'✅ enabled' if val else '❌ disabled'}")
    asyncio.create_task(auto_delete(msg, 5))
    asyncio.create_task(auto_delete(message, 3))


@handle_errors
@group_admin_only
@group_only
async def cmd_floodrate(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    if not args or not args[0].isdigit():
        await message.reply("Usage: /floodrate <number>")
        return
    val = int(args[0])
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, message.chat.id, flood_rate=val)
    msg = await message.reply(f"🌊 Flood rate set to {val} messages.")
    asyncio.create_task(auto_delete(msg, 5))
    asyncio.create_task(auto_delete(message, 3))


@handle_errors
@group_admin_only
@group_only
async def cmd_floodwindow(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    if not args or not args[0].isdigit():
        await message.reply("Usage: /floodwindow <seconds>")
        return
    val = int(args[0])
    async with AsyncSessionLocal() as session:
        await update_group_settings(session, message.chat.id, flood_window=val)
    msg = await message.reply(f"🌊 Flood window set to {val}s.")
    asyncio.create_task(auto_delete(msg, 5))
    asyncio.create_task(auto_delete(message, 3))


def register(app: Client) -> None:
    app.add_handler(
        MessageHandler(
            _handle_incoming,
            filters.group & ~filters.command([
                "mute","tmute","unmute","kick","ban","tban","unban",
                "warn","dwarn","unwarn","resetwarn","warns","del","stats",
                "purge","purgeme",
                "lock","unlock","locks","restrict","unrestrict",
                "antispam","antilink","antiflood","floodrate","floodwindow",
                "settings","rules","setrules","links","setlinks","setwelcome","setwarnlimit",
                "setwarnaction","setprefix","setlogchannel","setcmddelay",
                "setediteddelay","promote","demote","editrights","settitle","pin","unpin","adminlist",
                "adminpanel","addadmin","removeadmin","listadmins","start","help",
            ]),
        ),
        group=5,
    )
    app.add_handler(
        EditedMessageHandler(_handle_edited, filters.group),
        group=5,
    )
    app.add_handler(MessageHandler(cmd_antispam,    filters.command("antispam")   & filters.group))
    app.add_handler(MessageHandler(cmd_antilink,    filters.command("antilink")   & filters.group))
    app.add_handler(MessageHandler(cmd_antiflood,   filters.command("antiflood")  & filters.group))
    app.add_handler(MessageHandler(cmd_floodrate,   filters.command("floodrate")  & filters.group))
    app.add_handler(MessageHandler(cmd_floodwindow, filters.command("floodwindow") & filters.group))
