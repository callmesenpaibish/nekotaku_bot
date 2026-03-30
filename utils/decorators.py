"""utils/decorators.py — Permission-checking decorators for handlers."""

import functools
from typing import Callable
from telegram import Update
from telegram.ext import ContextTypes

import config as cfg
from utils.helpers import is_admin


def owner_only(func: Callable) -> Callable:
    """Restrict handler to bot owner only."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user or user.id != cfg.OWNER_ID:
            await update.effective_message.reply_text("⛔ Owner-only command.")
            return
        return await func(update, context)
    return wrapper


def group_admin_only(func: Callable) -> Callable:
    """Restrict handler to group admins (and owner)."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        chat = update.effective_chat
        if not user or not chat:
            return
        if user.id == cfg.OWNER_ID:
            return await func(update, context)
        if not await is_admin(chat, user.id, context):
            await update.effective_message.reply_text("⛔ Admin-only command.")
            return
        return await func(update, context)
    return wrapper


def group_only(func: Callable) -> Callable:
    """Restrict handler to group/supergroup chats only."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        if chat and chat.type == "private":
            await update.effective_message.reply_text(
                "❌ This command only works in group chats."
            )
            return
        return await func(update, context)
    return wrapper
