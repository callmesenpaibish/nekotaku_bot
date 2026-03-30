"""utils/helpers.py — Shared helper utilities."""

import asyncio
from typing import Optional
from telegram import Message, Update, User, Chat
from telegram.ext import ContextTypes
from telegram.error import BadRequest, TelegramError


def mention_html(user: User) -> str:
    """Return an HTML mention link for a user."""
    name = user.full_name or str(user.id)
    return f'<a href="tg://user?id={user.id}">{name}</a>'


def get_target_user(update: Update) -> Optional[User]:
    """
    Extract the target user from a reply or the command argument.
    Returns None if no target can be determined.
    """
    msg = update.effective_message
    if msg.reply_to_message:
        return msg.reply_to_message.from_user
    return None


async def safe_delete(message: Message) -> None:
    """Delete a message, silently ignoring if already deleted."""
    try:
        await message.delete()
    except (BadRequest, TelegramError):
        pass


async def auto_delete(message: Message, delay: int) -> None:
    """Delete a message after `delay` seconds."""
    if delay <= 0:
        return
    await asyncio.sleep(delay)
    await safe_delete(message)


async def is_admin(chat: Chat, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user_id is an admin in the given chat."""
    try:
        member = await context.bot.get_chat_member(chat.id, user_id)
        return member.status in ("administrator", "creator")
    except TelegramError:
        return False


def parse_command_args(text: str) -> list[str]:
    """Split command text into args, stripping the command itself."""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return []
    return parts[1].split()


def user_link(user: User) -> str:
    name = user.full_name or str(user.id)
    return f'<a href="tg://user?id={user.id}">{name}</a>'


def admin_link(user: User) -> str:
    return user_link(user)
