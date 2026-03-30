"""handlers/errors.py — Centralised error logging wrapper for Pyrogram."""

import logging
import traceback
import functools
from pyrogram.errors import FloodWait, RPCError

logger = logging.getLogger(__name__)


def handle_errors(func):
    """Decorator that catches and logs exceptions from any Pyrogram handler."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except FloodWait as e:
            logger.warning("FloodWait in %s: retry after %ds", func.__name__, e.value)
        except RPCError as e:
            logger.warning("RPCError in %s: %s", func.__name__, e)
        except Exception:
            logger.error("Unhandled exception in %s:\n%s", func.__name__, traceback.format_exc())
    return wrapper


def register(app) -> None:
    pass
