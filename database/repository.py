"""database/repository.py — All database queries (repository pattern)."""

import json
from typing import Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    GroupSettings, UserWarning, UserInfraction, AllowedAdmin, ActionLog
)
import config as cfg


# ── GroupSettings ─────────────────────────────────────────────────────────────

async def get_group_settings(session: AsyncSession, chat_id: int) -> GroupSettings:
    """Return group settings, creating defaults if not found."""
    result = await session.execute(
        select(GroupSettings).where(GroupSettings.chat_id == chat_id)
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = GroupSettings(
            chat_id=chat_id,
            flood_rate=cfg.FLOOD_RATE,
            flood_window=cfg.FLOOD_WINDOW,
            spam_mute_duration=cfg.SPAM_MUTE_DURATION,
            delete_cmd_delay=cfg.AUTO_DELETE_CMD_DELAY,
            delete_edited_delay=cfg.AUTO_DELETE_EDITED_DELAY,
            log_channel_id=cfg.LOG_CHANNEL_ID or None,
        )
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
    return settings


async def update_group_settings(session: AsyncSession, chat_id: int, **kwargs) -> None:
    settings = await get_group_settings(session, chat_id)
    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    await session.commit()


# ── Warnings ──────────────────────────────────────────────────────────────────

async def get_warn(
    session: AsyncSession, chat_id: int, user_id: int
) -> UserWarning:
    result = await session.execute(
        select(UserWarning).where(
            UserWarning.chat_id == chat_id,
            UserWarning.user_id == user_id,
        )
    )
    warn = result.scalar_one_or_none()
    if warn is None:
        warn = UserWarning(chat_id=chat_id, user_id=user_id, count=0, reasons="[]")
        session.add(warn)
        await session.commit()
        await session.refresh(warn)
    return warn


async def add_warn(
    session: AsyncSession, chat_id: int, user_id: int, reason: Optional[str] = None
) -> int:
    """Increment warn count. Returns new count."""
    warn = await get_warn(session, chat_id, user_id)
    warn.count += 1
    reasons = json.loads(warn.reasons or "[]")
    if reason:
        reasons.append(reason)
    warn.reasons = json.dumps(reasons)
    await session.commit()
    return warn.count


async def reset_warns(session: AsyncSession, chat_id: int, user_id: int) -> None:
    await session.execute(
        delete(UserWarning).where(
            UserWarning.chat_id == chat_id,
            UserWarning.user_id == user_id,
        )
    )
    await session.commit()


async def get_warn_count(session: AsyncSession, chat_id: int, user_id: int) -> int:
    warn = await get_warn(session, chat_id, user_id)
    return warn.count


# ── Infractions ───────────────────────────────────────────────────────────────

async def add_infraction(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    action_type: str,
    reason: Optional[str] = None,
    performed_by: Optional[int] = None,
) -> None:
    # Ensure group settings row exists
    await get_group_settings(session, chat_id)
    infraction = UserInfraction(
        chat_id=chat_id,
        user_id=user_id,
        action_type=action_type,
        reason=reason,
        performed_by=performed_by,
    )
    session.add(infraction)
    await session.commit()


async def get_infractions(
    session: AsyncSession, chat_id: int, user_id: int
) -> list[UserInfraction]:
    result = await session.execute(
        select(UserInfraction).where(
            UserInfraction.chat_id == chat_id,
            UserInfraction.user_id == user_id,
        )
    )
    return list(result.scalars().all())


# ── AllowedAdmins ─────────────────────────────────────────────────────────────

async def add_allowed_admin(
    session: AsyncSession, user_id: int, tier: str, added_by: int
) -> AllowedAdmin:
    existing = await get_allowed_admin(session, user_id)
    if existing:
        existing.tier = tier
        await session.commit()
        return existing
    admin = AllowedAdmin(user_id=user_id, tier=tier, added_by=added_by)
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    return admin


async def remove_allowed_admin(session: AsyncSession, user_id: int) -> bool:
    result = await session.execute(
        delete(AllowedAdmin).where(AllowedAdmin.user_id == user_id)
    )
    await session.commit()
    return result.rowcount > 0


async def get_allowed_admin(
    session: AsyncSession, user_id: int
) -> Optional[AllowedAdmin]:
    result = await session.execute(
        select(AllowedAdmin).where(AllowedAdmin.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_allowed_admins(session: AsyncSession) -> list[AllowedAdmin]:
    result = await session.execute(select(AllowedAdmin))
    return list(result.scalars().all())


# ── ActionLog ─────────────────────────────────────────────────────────────────

async def log_action(
    session: AsyncSession,
    chat_id: int,
    action: str,
    target_user_id: Optional[int] = None,
    target_username: Optional[str] = None,
    admin_id: Optional[int] = None,
    admin_username: Optional[str] = None,
    reason: Optional[str] = None,
    duration: Optional[int] = None,
    extra: Optional[str] = None,
) -> None:
    await get_group_settings(session, chat_id)  # ensure group row
    entry = ActionLog(
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
    session.add(entry)
    await session.commit()
