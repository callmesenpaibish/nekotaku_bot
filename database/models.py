"""database/models.py — ORM models for all persistent data."""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey,
    Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.engine import Base


# ── Group-level settings ──────────────────────────────────────────────────────

class GroupSettings(Base):
    __tablename__ = "group_settings"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Welcome
    welcome_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    welcome_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Auto-delete timings (seconds; 0 = disabled)
    delete_cmd_delay: Mapped[int] = mapped_column(Integer, default=3)
    delete_edited_delay: Mapped[int] = mapped_column(Integer, default=25)
    delete_join_msg: Mapped[bool] = mapped_column(Boolean, default=True)
    delete_left_msg: Mapped[bool] = mapped_column(Boolean, default=True)

    # Anti-spam
    antispam_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    antilink_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    antiforward_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    flood_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    flood_rate: Mapped[int] = mapped_column(Integer, default=5)
    flood_window: Mapped[int] = mapped_column(Integer, default=5)
    spam_mute_duration: Mapped[int] = mapped_column(Integer, default=600)

    # Warn system
    warn_limit: Mapped[int] = mapped_column(Integer, default=3)
    warn_action: Mapped[str] = mapped_column(String(10), default="mute")

    # Locks (comma-separated types: link, sticker, image, video, forward, audio, document)
    locked_types: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="")

    # Log channel
    log_channel_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    log_cleanup: Mapped[bool] = mapped_column(Boolean, default=False)

    # Command prefix per group
    prefix: Mapped[str] = mapped_column(String(5), default=".")

    # Rules text
    rules: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Feature toggles
    antilink_allow_admins: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    warnings: Mapped[list["UserWarning"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    infractions: Mapped[list["UserInfraction"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    logs: Mapped[list["ActionLog"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


# ── Per-user warnings ─────────────────────────────────────────────────────────

class UserWarning(Base):
    __tablename__ = "user_warnings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("group_settings.chat_id", ondelete="CASCADE")
    )
    user_id: Mapped[int] = mapped_column(BigInteger)
    count: Mapped[int] = mapped_column(Integer, default=0)
    reasons: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list

    group: Mapped["GroupSettings"] = relationship(back_populates="warnings")


# ── Per-user infraction tracking ──────────────────────────────────────────────

class UserInfraction(Base):
    __tablename__ = "user_infractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("group_settings.chat_id", ondelete="CASCADE")
    )
    user_id: Mapped[int] = mapped_column(BigInteger)
    action_type: Mapped[str] = mapped_column(String(20))  # mute | kick | ban | warn | spam
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    performed_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    group: Mapped["GroupSettings"] = relationship(back_populates="infractions")


# ── Owner-managed admin access list ───────────────────────────────────────────

class AllowedAdmin(Base):
    __tablename__ = "allowed_admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    # Tier: "full" | "limited" | "group_only" | "readonly"
    tier: Mapped[str] = mapped_column(String(20), default="full")
    added_by: Mapped[int] = mapped_column(BigInteger)
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── Moderation action log ─────────────────────────────────────────────────────

class ActionLog(Base):
    __tablename__ = "action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("group_settings.chat_id", ondelete="CASCADE")
    )
    action: Mapped[str] = mapped_column(String(30))
    target_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    target_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    admin_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    admin_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # seconds
    extra: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    group: Mapped["GroupSettings"] = relationship(back_populates="logs")
