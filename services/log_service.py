"""services/log_service.py — Send structured moderation logs to a channel/group."""

import logging
from datetime import datetime, timezone
from typing import Optional
from pyrogram import Client

from database.engine import AsyncSessionLocal
from database.repository import get_group_settings, log_action as db_log_action

logger = logging.getLogger(__name__)

# Cache of peer-resolved log channel IDs (avoid re-fetching on every action)
_resolved_channels: dict[int, int] = {}


async def _resolve_log_channel(client: Client, channel_id: int) -> Optional[int]:
    """
    Resolve a log channel ID.
    Pyrogram 2.0.x does not support 64-bit channel IDs (those > 2^31).
    We try to join/resolve the peer; if it fails we log a warning and return None.
    """
    if channel_id in _resolved_channels:
        return _resolved_channels[channel_id]
    try:
        chat = await client.get_chat(channel_id)
        _resolved_channels[channel_id] = chat.id
        return chat.id
    except Exception as e:
        logger.warning(
            "Log channel %d could not be resolved by Pyrogram: %s. "
            "If the channel was created recently it may use a 64-bit ID not "
            "supported by Pyrogram 2.0.x — try forwarding a message from the "
            "channel to the bot so it caches the peer.",
            channel_id, e,
        )
        return None


async def send_log(
    client: Client,
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
    from utils.time_parser import seconds_to_human

    # ── Always write to DB regardless of channel availability ─────────────────
    try:
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
    except Exception as e:
        logger.warning("Failed to write action log to DB: %s", e)
        return

    if not log_dest:
        return

    # ── Build the log message ─────────────────────────────────────────────────
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    target_str = f"@{target_username}" if target_username else f"ID:{target_user_id}"
    admin_str = (
        "🤖 Auto" if auto
        else f"@{admin_username}" if admin_username
        else f"ID:{admin_id}"
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

    # ── Send to channel — catch ALL exceptions so nothing breaks commands ──────
    try:
        resolved = await _resolve_log_channel(client, log_dest)
        if resolved is None:
            return
        await client.send_message(
            chat_id=resolved,
            text="\n".join(lines),
        )
    except Exception as e:
        logger.warning("Failed to send log to channel %d: %s", log_dest, e)
