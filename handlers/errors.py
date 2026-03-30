"""handlers/errors.py — Global error handler for the application."""

import logging
import traceback
from telegram import Update
from telegram.error import (
    BadRequest, Forbidden, NetworkError, TimedOut, RetryAfter
)
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log all errors raised by handlers."""
    err = context.error

    # Network errors — log at WARNING level, not ERROR (expected in long polling)
    if isinstance(err, (NetworkError, TimedOut)):
        logger.warning("Network error: %s", err)
        return

    if isinstance(err, RetryAfter):
        logger.warning("Rate limited — retry after %.1f seconds", err.retry_after)
        return

    # Forbidden — bot was kicked or lacks permissions
    if isinstance(err, Forbidden):
        logger.warning("Forbidden: %s", err)
        return

    # Bad request — usually an API usage mistake
    if isinstance(err, BadRequest):
        logger.warning("BadRequest: %s", err)
        return

    # Everything else — log full traceback
    tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))
    logger.error("Unhandled exception:\n%s", tb)

    # Optionally notify the update sender
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ An internal error occurred. The issue has been logged."
            )
        except Exception:
            pass


def register(application) -> None:
    application.add_error_handler(error_handler)
