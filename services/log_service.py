"""services/log_service.py — Send structured moderation logs to a channel/group."""

import asyncio
from datetime import datetime, timezone
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError

from database.engine import AsyncSessionLocal
from database.repository import get_group_settings, log_action as db_log_action


async def send_log(
    bot: Bot,
    chat_id: int,
    action: str,
    *,
    target_user_id: Optional[int] = None,
    target_username: Optional[str] = None,
    admin_id: Optional[int] = None,
    admin_username: Optional[str] = None,
    reason: Optional[str] = None,
    duration: Optional[int] = None,
    extra: Optional[str] = None,
    auto: bool = False,
) -> None:
    """
    Persist the log entry to DB and forward a structured message to the
    configured log channel/group for the given chat.
    """
    from utils.time_parser import seconds_to_human

    async with AsyncSessionLocal() as session:
        settings = await get_group_settings(session, chat_id)
        log_dest = settings.log_channel_id

        await db_log_action(
            session,
            chat_id=chat_id,
            action=action,
            target_user_id=target_user_id,
            target_username=target_username,
            admin_id=admin_id,
            admin_username=admin_username,
            reason=reason,
            duration=duration,
            extra=extra,
        )

    if not log_dest:
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    target_str = f"@{target_username}" if target_username else f"ID:{target_user_id}"
    admin_str  = f"@{admin_username}" if admin_username else (
        "🤖 Auto" if auto else f"ID:{admin_id}"
    )

    lines = [
        f"📋 <b>Action:</b> <code>{action.upper()}</code>",
        f"👤 <b>Target:</b> {target_str}",
        f"🛡 <b>By:</b> {admin_str}" + (" <i>(automatic)</i>" if auto else ""),
    ]
    if reason:
        lines.append(f"📝 <b>Reason:</b> {reason}")
    if duration:
        lines.append(f"⏱ <b>Duration:</b> {seconds_to_human(duration)}")
    if extra:
        lines.append(f"ℹ️ <b>Note:</b> {extra}")
    lines.append(f"🕐 <b>Time:</b> {now}")

    text = "\n".join(lines)
    try:
        await bot.send_message(
            chat_id=log_dest,
            text=text,
            parse_mode="HTML",
        )
    except TelegramError:
        pass  # Log destination unreachable — fail silently
