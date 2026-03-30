"""handlers/moderation.py — Mute, kick, ban, warn, del commands."""

import asyncio
import json
from typing import Optional, Tuple
from pyrogram import Client, filters
from pyrogram.types import Message, User
from pyrogram.handlers import MessageHandler
from pyrogram.errors import RPCError

import config as cfg
from database.engine import AsyncSessionLocal
from database.repository import (
    get_group_settings, add_warn, reset_warns, get_warn_count,
    get_infractions, get_warn,
)
from services.moderation_service import (
    mute_user, unmute_user, kick_user, ban_user, unban_user
)
from utils.decorators import group_admin_only, group_only
from utils.helpers import safe_delete, auto_delete, mention_html, is_admin
from utils.time_parser import parse_duration, seconds_to_human
from handlers.errors import handle_errors


async def _resolve_target(
    client: Client, message: Message, args: list[str]
) -> Tuple[Optional[User], list[str]]:
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user, args

    if args:
        identifier = args[0]
        rest = args[1:]
        try:
            if identifier.startswith("@") or identifier.lstrip("-").isdigit():
                uid = int(identifier) if identifier.lstrip("-").isdigit() else identifier
                member = await client.get_chat_member(message.chat.id, uid)
                return member.user, list(rest)
        except RPCError:
            await message.reply("❌ User not found.")
            return None, []

    await message.reply("❌ Reply to a user or specify @username / user ID.")
    return None, []


def _guard_target(target: User, admin: User) -> Optional[str]:
    if target.id == cfg.OWNER_ID:
        return "⛔ You cannot moderate the bot owner."
    if target.id == admin.id:
        return "⛔ You cannot moderate yourself."
    if target.is_bot:
        return "⛔ Cannot moderate bots."
    return None


async def _reply_and_autodelete(message: Message, text: str, delay: int = 5) -> None:
    msg = await message.reply(text)
    asyncio.create_task(auto_delete(msg, delay))
    asyncio.create_task(auto_delete(message, 3))


@handle_errors
@group_admin_only
@group_only
async def cmd_mute(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    target, args = await _resolve_target(client, message, args)
    if not target:
        return
    err = _guard_target(target, message.from_user)
    if err:
        await _reply_and_autodelete(message, err)
        return
    reason = " ".join(args) if args else None
    ok = await mute_user(client, message.chat.id, target, admin=message.from_user, reason=reason)
    if ok:
        await _reply_and_autodelete(
            message,
            f"🔇 {mention_html(target)} has been muted."
            + (f"\n📝 Reason: {reason}" if reason else ""),
        )


@handle_errors
@group_admin_only
@group_only
async def cmd_tmute(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    target, args = await _resolve_target(client, message, args)
    if not target:
        return
    err = _guard_target(target, message.from_user)
    if err:
        await _reply_and_autodelete(message, err)
        return
    if not args:
        await _reply_and_autodelete(message, "❌ Usage: /tmute @user &lt;duration&gt; [reason]\nExample: /tmute @user 10m")
        return
    duration = parse_duration(args[0])
    if not duration:
        await _reply_and_autodelete(message, "❌ Invalid duration. Examples: 10m, 2h, 1d, 45s")
        return
    reason = " ".join(args[1:]) if args[1:] else None
    ok = await mute_user(client, message.chat.id, target, admin=message.from_user, reason=reason, duration=duration)
    if ok:
        await _reply_and_autodelete(
            message,
            f"🔇 {mention_html(target)} muted for <b>{seconds_to_human(duration)}</b>."
            + (f"\n📝 Reason: {reason}" if reason else ""),
        )


@handle_errors
@group_admin_only
@group_only
async def cmd_unmute(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    target, _ = await _resolve_target(client, message, args)
    if not target:
        return
    ok = await unmute_user(client, message.chat.id, target, admin=message.from_user)
    if ok:
        await _reply_and_autodelete(message, f"🔊 {mention_html(target)} has been unmuted.")


@handle_errors
@group_admin_only
@group_only
async def cmd_kick(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    target, args = await _resolve_target(client, message, args)
    if not target:
        return
    err = _guard_target(target, message.from_user)
    if err:
        await _reply_and_autodelete(message, err)
        return
    reason = " ".join(args) if args else None
    ok = await kick_user(client, message.chat.id, target, admin=message.from_user, reason=reason)
    if ok:
        await _reply_and_autodelete(
            message,
            f"👢 {mention_html(target)} has been kicked."
            + (f"\n📝 Reason: {reason}" if reason else ""),
        )


@handle_errors
@group_admin_only
@group_only
async def cmd_ban(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    target, args = await _resolve_target(client, message, args)
    if not target:
        return
    err = _guard_target(target, message.from_user)
    if err:
        await _reply_and_autodelete(message, err)
        return
    reason = " ".join(args) if args else None
    ok = await ban_user(client, message.chat.id, target, admin=message.from_user, reason=reason)
    if ok:
        await _reply_and_autodelete(
            message,
            f"🔨 {mention_html(target)} has been banned."
            + (f"\n📝 Reason: {reason}" if reason else ""),
        )


@handle_errors
@group_admin_only
@group_only
async def cmd_tban(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    target, args = await _resolve_target(client, message, args)
    if not target:
        return
    err = _guard_target(target, message.from_user)
    if err:
        await _reply_and_autodelete(message, err)
        return
    if not args:
        await _reply_and_autodelete(message, "❌ Usage: /tban @user &lt;duration&gt; [reason]")
        return
    duration = parse_duration(args[0])
    if not duration:
        await _reply_and_autodelete(message, "❌ Invalid duration.")
        return
    reason = " ".join(args[1:]) if args[1:] else None
    ok = await ban_user(client, message.chat.id, target, admin=message.from_user, reason=reason, duration=duration)
    if ok:
        await _reply_and_autodelete(
            message,
            f"🔨 {mention_html(target)} banned for <b>{seconds_to_human(duration)}</b>."
            + (f"\n📝 Reason: {reason}" if reason else ""),
        )


@handle_errors
@group_admin_only
@group_only
async def cmd_unban(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    target, _ = await _resolve_target(client, message, args)
    if not target:
        return
    ok = await unban_user(client, message.chat.id, target, admin=message.from_user)
    if ok:
        await _reply_and_autodelete(message, f"✅ {mention_html(target)} has been unbanned.")


@handle_errors
@group_admin_only
@group_only
async def cmd_warn(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    target, args = await _resolve_target(client, message, args)
    if not target:
        return
    err = _guard_target(target, message.from_user)
    if err:
        await _reply_and_autodelete(message, err)
        return

    reason = " ".join(args) if args else None
    chat_id = message.chat.id

    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat_id)
        count = await add_warn(session, chat_id, target.id, reason=reason)
        warn_limit = settings.warn_limit
        warn_action = settings.warn_action

    reply = (
        f"⚠️ {mention_html(target)} warned. "
        f"(<b>{count}/{warn_limit}</b>)"
        + (f"\n📝 Reason: {reason}" if reason else "")
    )

    if count >= warn_limit:
        reply += f"\n\n🚨 Warn limit reached — applying <b>{warn_action}</b>!"
        if warn_action == "mute":
            await mute_user(client, chat_id, target, admin=message.from_user, reason="Warn limit reached")
        elif warn_action == "kick":
            await kick_user(client, chat_id, target, admin=message.from_user, reason="Warn limit reached")
        elif warn_action == "ban":
            await ban_user(client, chat_id, target, admin=message.from_user, reason="Warn limit reached")
        async with AsyncSessionLocal() as session:
            await reset_warns(session, chat_id, target.id)

    await _reply_and_autodelete(message, reply)


@handle_errors
@group_admin_only
@group_only
async def cmd_dwarn(client: Client, message: Message) -> None:
    if message.reply_to_message:
        await safe_delete(message.reply_to_message)
    await cmd_warn(client, message)


@handle_errors
@group_admin_only
@group_only
async def cmd_unwarn(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    target, _ = await _resolve_target(client, message, args)
    if not target:
        return
    chat_id = message.chat.id
    async with AsyncSessionLocal() as session:
        w = await get_warn(session, chat_id, target.id)
        w.count = max(0, w.count - 1)
        await session.commit()
    await _reply_and_autodelete(message, f"✅ One warning removed from {mention_html(target)}.")


@handle_errors
@group_admin_only
@group_only
async def cmd_resetwarn(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    target, _ = await _resolve_target(client, message, args)
    if not target:
        return
    async with AsyncSessionLocal() as session:
        await reset_warns(session, message.chat.id, target.id)
    await _reply_and_autodelete(message, f"✅ All warnings for {mention_html(target)} have been reset.")


@handle_errors
@group_admin_only
@group_only
async def cmd_warns(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    target, _ = await _resolve_target(client, message, args)
    if not target:
        return
    chat_id = message.chat.id
    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat_id)
        count = await get_warn_count(session, chat_id, target.id)
    await _reply_and_autodelete(
        message,
        f"⚠️ {mention_html(target)}: <b>{count}/{settings.warn_limit}</b> warnings.",
    )


@handle_errors
@group_admin_only
@group_only
async def cmd_del(client: Client, message: Message) -> None:
    if message.reply_to_message:
        await safe_delete(message.reply_to_message)
    await safe_delete(message)


@handle_errors
@group_admin_only
@group_only
async def cmd_stats(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    target, _ = await _resolve_target(client, message, args)
    if not target:
        return
    chat_id = message.chat.id
    async with AsyncSessionLocal() as session:
        infractions = await get_infractions(session, chat_id, target.id)
        warns = await get_warn_count(session, chat_id, target.id)

    if not infractions:
        await _reply_and_autodelete(
            message,
            f"📊 {mention_html(target)} has a clean record. No infractions recorded.",
        )
        return

    lines = [f"📊 <b>Stats for {mention_html(target)}</b>", f"⚠️ Active warnings: {warns}\n"]
    for inf in infractions[-10:]:
        lines.append(f"• <code>{inf.action_type.upper()}</code> — {inf.reason or 'No reason'} ({inf.created_at.strftime('%Y-%m-%d')})")

    await _reply_and_autodelete(message, "\n".join(lines), delay=10)


# ── Custom prefix handler (e.g. .mute, .ban) ─────────────────────────────────

@handle_errors
async def _prefix_handler(client: Client, message: Message) -> None:
    if not message.text or not message.from_user:
        return

    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, message.chat.id)
    prefix = settings.prefix or cfg.DEFAULT_PREFIX

    text = message.text.strip()
    if not text.startswith(prefix):
        return

    parts = text[len(prefix):].split()
    if not parts:
        return

    cmd = parts[0].lower()
    args = parts[1:]

    # Temporarily inject command into message for consistent handling
    message.command = [cmd] + args

    routing = {
        "mute": cmd_mute,
        "tmute": cmd_tmute,
        "unmute": cmd_unmute,
        "kick": cmd_kick,
        "tkick": cmd_kick,
        "ban": cmd_ban,
        "tban": cmd_tban,
        "unban": cmd_unban,
        "warn": cmd_warn,
        "dwarn": cmd_dwarn,
        "unwarn": cmd_unwarn,
        "resetwarn": cmd_resetwarn,
        "warns": cmd_warns,
        "del": cmd_del,
    }

    handler_fn = routing.get(cmd)
    if handler_fn:
        await handler_fn(client, message)


def register(app: Client) -> None:
    app.add_handler(MessageHandler(cmd_mute,      filters.command("mute")      & filters.group))
    app.add_handler(MessageHandler(cmd_tmute,     filters.command("tmute")     & filters.group))
    app.add_handler(MessageHandler(cmd_unmute,    filters.command("unmute")    & filters.group))
    app.add_handler(MessageHandler(cmd_kick,      filters.command("kick")      & filters.group))
    app.add_handler(MessageHandler(cmd_ban,       filters.command("ban")       & filters.group))
    app.add_handler(MessageHandler(cmd_tban,      filters.command("tban")      & filters.group))
    app.add_handler(MessageHandler(cmd_unban,     filters.command("unban")     & filters.group))
    app.add_handler(MessageHandler(cmd_warn,      filters.command("warn")      & filters.group))
    app.add_handler(MessageHandler(cmd_dwarn,     filters.command("dwarn")     & filters.group))
    app.add_handler(MessageHandler(cmd_unwarn,    filters.command("unwarn")    & filters.group))
    app.add_handler(MessageHandler(cmd_resetwarn, filters.command("resetwarn") & filters.group))
    app.add_handler(MessageHandler(cmd_warns,     filters.command("warns")     & filters.group))
    app.add_handler(MessageHandler(cmd_del,       filters.command("del")       & filters.group))
    app.add_handler(MessageHandler(cmd_stats,     filters.command("stats")     & filters.group))
    app.add_handler(MessageHandler(_prefix_handler, filters.group & filters.text), group=10)
