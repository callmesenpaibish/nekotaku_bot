"""utils/decorators.py — Permission-checking decorators for Pyrogram handlers."""

import functools
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.enums import ChatType

import config as cfg
from utils.helpers import is_admin


def owner_only(func):
    @functools.wraps(func)
    async def wrapper(client: Client, message: Message):
        if not message.from_user or message.from_user.id != cfg.OWNER_ID:
            await message.reply("⛔ Owner-only command.")
            return
        return await func(client, message)
    return wrapper


def group_admin_only(func):
    @functools.wraps(func)
    async def wrapper(client: Client, message: Message):
        if not message.from_user:
            return
        if message.from_user.id == cfg.OWNER_ID:
            return await func(client, message)
        if not await is_admin(client, message.chat.id, message.from_user.id):
            await message.reply("⛔ Admin-only command.")
            return
        return await func(client, message)
    return wrapper


def group_only(func):
    @functools.wraps(func)
    async def wrapper(client: Client, message: Message):
        if message.chat.type == ChatType.PRIVATE:
            await message.reply("❌ This command only works in group chats.")
            return
        return await func(client, message)
    return wrapper
