"""handlers/moderation.py — Mute, kick, ban, warn, del commands."""

import asyncio
import re
from typing import Optional, Tuple
from telegram import Update, User
from telegram.ext import ContextTypes, MessageHandler, CommandHandler, filters

import config as cfg
from database.engine import AsyncSessionLocal
from database.repository import (
    get_group_settings, add_warn, reset_warns, get_warn_count,
    get_infractions,
)
from services.moderation_service import (
    mute_user, unmute_user, kick_user, ban_user, unban_user
)
from utils.decorators import group_admin_only, group_only
from utils.helpers import safe_delete, auto_delete, mention_html, is_admin
from utils.time_parser import parse_duration, seconds_to_human


# ── Shared helper: extract target + optional duration + reason ────────────────

async def _resolve_target(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> Tuple[Optional[User], list[str]]:
    """
    Returns (target_user, remaining_args).
    Target is resolved from:
      1. Reply-to message
      2. @username or user_id in args
    """
    msg = update.effective_message
    args = context.args or []

    # From reply
    if msg.reply_to_message and msg.reply_to_message.from_user:
        return msg.reply_to_message.from_user, args

    # From first arg (@username or numeric ID)
    if args:
        identifier = args[0]
        rest = args[1:]
        if identifier.startswith("@"):
            try:
                member = await context.bot.get_chat_member(
                    update.effective_chat.id, identifier
                )
                return member.user, list(rest)
            except Exception:
                await msg.reply_text("❌ User not found.")
                return None, []
        elif identifier.lstrip("-").isdigit():
            try:
                member = await context.bot.get_chat_member(
                    update.effective_chat.id, int(identifier)
                )
                return member.user, list(rest)
            except Exception:
                await msg.reply_text("❌ User not found.")
                return None, []

    await msg.reply_text("❌ Reply to a user or specify @username / user ID.")
    return None, []


def _guard_target(target: User, admin: User) -> Optional[str]:
    """Return error string if targeting the bot owner or same admin."""
    if target.id == cfg.OWNER_ID:
        return "⛔ You cannot moderate the bot owner."
    if target.id == admin.id:
        return "⛔ You cannot moderate yourself."
    if target.is_bot:
        return "⛔ Cannot moderate bots."
    return None


async def _reply_and_autodelete(
    update: Update, text: str, delay: int = 5
) -> None:
    msg = await update.effective_message.reply_text(text, parse_mode="HTML")
    asyncio.create_task(auto_delete(msg, delay))
    asyncio.create_task(auto_delete(update.effective_message, 3))


# ── .mute / .tmute ────────────────────────────────────────────────────────────

@group_admin_only
@group_only
async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target, args = await _resolve_target(update, context)
    if not target:
        return

    err = _guard_target(target, update.effective_user)
    if err:
        await _reply_and_autodelete(update, err)
        return

    reason = " ".join(args) if args else None
    ok = await mute_user(
        context.bot, update.effective_chat.id, target,
        admin=update.effective_user, reason=reason,
    )
    if ok:
        await _reply_and_autodelete(
            update,
            f"🔇 {mention_html(target)} has been muted."
            + (f"\n📝 Reason: {reason}" if reason else ""),
        )


@group_admin_only
@group_only
async def cmd_tmute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target, args = await _resolve_target(update, context)
    if not target:
        return

    err = _guard_target(target, update.effective_user)
    if err:
        await _reply_and_autodelete(update, err)
        return

    if not args:
        await _reply_and_autodelete(update, "❌ Usage: .tmute @user &lt;duration&gt; [reason]\nExample: .tmute @user 10m")
        return

    duration = parse_duration(args[0])
    if not duration:
        await _reply_and_autodelete(update, "❌ Invalid duration. Examples: 10m, 2h, 1d, 45s")
        return

    reason = " ".join(args[1:]) if args[1:] else None
    ok = await mute_user(
        context.bot, update.effective_chat.id, target,
        admin=update.effective_user,
        reason=reason,
        duration=duration,
    )
    if ok:
        await _reply_and_autodelete(
            update,
            f"🔇 {mention_html(target)} muted for <b>{seconds_to_human(duration)}</b>."
            + (f"\n📝 Reason: {reason}" if reason else ""),
        )


@group_admin_only
@group_only
async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target, _ = await _resolve_target(update, context)
    if not target:
        return
    ok = await unmute_user(context.bot, update.effective_chat.id, target, admin=update.effective_user)
    if ok:
        await _reply_and_autodelete(update, f"🔊 {mention_html(target)} has been unmuted.")


# ── .kick / .tkick ────────────────────────────────────────────────────────────

@group_admin_only
@group_only
async def cmd_kick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target, args = await _resolve_target(update, context)
    if not target:
        return
    err = _guard_target(target, update.effective_user)
    if err:
        await _reply_and_autodelete(update, err)
        return
    reason = " ".join(args) if args else None
    ok = await kick_user(
        context.bot, update.effective_chat.id, target,
        admin=update.effective_user, reason=reason,
    )
    if ok:
        await _reply_and_autodelete(
            update,
            f"👢 {mention_html(target)} has been kicked."
            + (f"\n📝 Reason: {reason}" if reason else ""),
        )


# ── .ban / .tban ──────────────────────────────────────────────────────────────

@group_admin_only
@group_only
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target, args = await _resolve_target(update, context)
    if not target:
        return
    err = _guard_target(target, update.effective_user)
    if err:
        await _reply_and_autodelete(update, err)
        return
    reason = " ".join(args) if args else None
    ok = await ban_user(
        context.bot, update.effective_chat.id, target,
        admin=update.effective_user, reason=reason,
    )
    if ok:
        await _reply_and_autodelete(
            update,
            f"🔨 {mention_html(target)} has been banned."
            + (f"\n📝 Reason: {reason}" if reason else ""),
        )


@group_admin_only
@group_only
async def cmd_tban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target, args = await _resolve_target(update, context)
    if not target:
        return
    err = _guard_target(target, update.effective_user)
    if err:
        await _reply_and_autodelete(update, err)
        return
    if not args:
        await _reply_and_autodelete(update, "❌ Usage: .tban @user &lt;duration&gt; [reason]")
        return
    duration = parse_duration(args[0])
    if not duration:
        await _reply_and_autodelete(update, "❌ Invalid duration.")
        return
    reason = " ".join(args[1:]) if args[1:] else None
    ok = await ban_user(
        context.bot, update.effective_chat.id, target,
        admin=update.effective_user, reason=reason, duration=duration,
    )
    if ok:
        await _reply_and_autodelete(
            update,
            f"🔨 {mention_html(target)} banned for <b>{seconds_to_human(duration)}</b>."
            + (f"\n📝 Reason: {reason}" if reason else ""),
        )


@group_admin_only
@group_only
async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target, _ = await _resolve_target(update, context)
    if not target:
        return
    ok = await unban_user(context.bot, update.effective_chat.id, target, admin=update.effective_user)
    if ok:
        await _reply_and_autodelete(update, f"✅ {mention_html(target)} has been unbanned.")


# ── .warn / .dwarn / .unwarn / .resetwarn / .warns ───────────────────────────

@group_admin_only
@group_only
async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target, args = await _resolve_target(update, context)
    if not target:
        return
    err = _guard_target(target, update.effective_user)
    if err:
        await _reply_and_autodelete(update, err)
        return

    reason = " ".join(args) if args else None
    chat_id = update.effective_chat.id

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
            await mute_user(context.bot, chat_id, target, admin=update.effective_user, reason="Warn limit reached")
        elif warn_action == "kick":
            await kick_user(context.bot, chat_id, target, admin=update.effective_user, reason="Warn limit reached")
        elif warn_action == "ban":
            await ban_user(context.bot, chat_id, target, admin=update.effective_user, reason="Warn limit reached")

        async with AsyncSessionLocal() as session:
            await reset_warns(session, chat_id, target.id)

    await _reply_and_autodelete(update, reply)


@group_admin_only
@group_only
async def cmd_dwarn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Warn + delete the replied-to message."""
    if update.effective_message.reply_to_message:
        await safe_delete(update.effective_message.reply_to_message)
    await cmd_warn(update, context)


@group_admin_only
@group_only
async def cmd_unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target, _ = await _resolve_target(update, context)
    if not target:
        return
    chat_id = update.effective_chat.id
    async with AsyncSessionLocal() as session:
        warn = await get_warn_count(session, chat_id, target.id)
        if warn > 0:
            from database.repository import get_warn
            w = await get_warn(session, chat_id, target.id)
            w.count = max(0, w.count - 1)
            await session.commit()
    await _reply_and_autodelete(update, f"✅ One warning removed from {mention_html(target)}.")


@group_admin_only
@group_only
async def cmd_resetwarn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target, _ = await _resolve_target(update, context)
    if not target:
        return
    async with AsyncSessionLocal() as session:
        await reset_warns(session, update.effective_chat.id, target.id)
    await _reply_and_autodelete(update, f"✅ All warnings for {mention_html(target)} have been reset.")


@group_admin_only
@group_only
async def cmd_warns(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target, _ = await _resolve_target(update, context)
    if not target:
        return
    chat_id = update.effective_chat.id
    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat_id)
        count = await get_warn_count(session, chat_id, target.id)
    await _reply_and_autodelete(
        update,
        f"⚠️ {mention_html(target)}: <b>{count}/{settings.warn_limit}</b> warnings.",
    )


# ── .del — delete replied message ─────────────────────────────────────────────

@group_admin_only
@group_only
async def cmd_del(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg.reply_to_message:
        await safe_delete(msg.reply_to_message)
    await safe_delete(msg)


# ── User stats ────────────────────────────────────────────────────────────────

@group_admin_only
@group_only
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target, _ = await _resolve_target(update, context)
    if not target:
        return
    chat_id = update.effective_chat.id
    async with AsyncSessionLocal() as session:
        infractions = await get_infractions(session, chat_id, target.id)
        warns = await get_warn_count(session, chat_id, target.id)

    if not infractions:
        await _reply_and_autodelete(
            update,
            f"📊 {mention_html(target)} has a clean record. No infractions recorded.",
        )
        return

    lines = [f"📊 <b>Stats for {mention_html(target)}</b>", f"⚠️ Active warnings: {warns}\n"]
    for inf in infractions[-10:]:  # last 10
        lines.append(f"• <code>{inf.action_type.upper()}</code> — {inf.reason or 'No reason'} ({inf.created_at.strftime('%Y-%m-%d')})")

    await _reply_and_autodelete(update, "\n".join(lines), delay=10)


# ── Custom prefix handler (e.g. .mute, .ban) ─────────────────────────────────

async def _prefix_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Route messages starting with the group's custom prefix to the right command.
    Allows commands like `.tmute @user 10m`.
    """
    msg = update.effective_message
    if not msg or not msg.text:
        return
    chat = update.effective_chat
    if not chat or chat.type == "private":
        return

    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat.id)
    prefix = settings.prefix or cfg.DEFAULT_PREFIX

    text = msg.text.strip()
    if not text.startswith(prefix):
        return

    parts = text[len(prefix):].split()
    if not parts:
        return

    cmd = parts[0].lower()
    # Inject args so decorators' context.args works
    context.args = parts[1:]

    routing = {
        "mute": cmd_mute,
        "tmute": cmd_tmute,
        "unmute": cmd_unmute,
        "kick": cmd_kick,
        "tkick": cmd_kick,  # tkick same as kick (Telegram handles duration via tban)
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
        await handler_fn(update, context)


def register(application) -> None:
    application.add_handler(CommandHandler("mute",      cmd_mute))
    application.add_handler(CommandHandler("tmute",     cmd_tmute))
    application.add_handler(CommandHandler("unmute",    cmd_unmute))
    application.add_handler(CommandHandler("kick",      cmd_kick))
    application.add_handler(CommandHandler("ban",       cmd_ban))
    application.add_handler(CommandHandler("tban",      cmd_tban))
    application.add_handler(CommandHandler("unban",     cmd_unban))
    application.add_handler(CommandHandler("warn",      cmd_warn))
    application.add_handler(CommandHandler("dwarn",     cmd_dwarn))
    application.add_handler(CommandHandler("unwarn",    cmd_unwarn))
    application.add_handler(CommandHandler("resetwarn", cmd_resetwarn))
    application.add_handler(CommandHandler("warns",     cmd_warns))
    application.add_handler(CommandHandler("del",       cmd_del))
    application.add_handler(CommandHandler("stats",     cmd_stats))

    # Prefix-based handler (lower priority than commands)
    application.add_handler(
        MessageHandler(filters.ChatType.GROUPS & filters.TEXT, _prefix_handler),
        group=10,
    )
