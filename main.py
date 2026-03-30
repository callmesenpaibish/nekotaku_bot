"""main.py — Entry point. Builds the Application and starts the bot."""

import logging
import os

from telegram.ext import Application, Defaults
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest

import config as cfg
from database.engine import init_db

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Silence noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def build_application() -> Application:
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=15.0,
        read_timeout=30.0,
        write_timeout=15.0,
        pool_timeout=15.0,
    )
    app = (
        Application.builder()
        .token(cfg.BOT_TOKEN)
        .defaults(Defaults(parse_mode=ParseMode.HTML))
        .request(request)
        .build()
    )
    return app


def register_all_handlers(app: Application) -> None:
    """Import and register all handler modules in the correct priority order."""
    from handlers import (
        errors,
        help,
        welcome,
        antispam,
        locks,
        moderation,
        settings,
        admin_tools,
        owner,
    )

    # Error handler first (catches everything)
    errors.register(app)

    # Core handlers
    help.register(app)
    welcome.register(app)
    owner.register(app)
    admin_tools.register(app)
    settings.register(app)
    locks.register(app)
    moderation.register(app)

    # Anti-spam LAST so it doesn't intercept command messages
    antispam.register(app)

    logger.info("All handlers registered.")


async def post_init(app: Application) -> None:
    """Run once after the bot initialises: set up DB and log readiness."""
    await init_db()
    logger.info("Database initialised.")

    me = await app.bot.get_me()
    logger.info("Bot started: @%s (id=%d)", me.username, me.id)

    # Notify owner
    try:
        await app.bot.send_message(
            chat_id=cfg.OWNER_ID,
            text=(
                f"✅ <b>Bot online</b>\n"
                f"Username: @{me.username}\n"
                f"ID: <code>{me.id}</code>\n\n"
                "Send /help to see available commands."
            ),
        )
    except Exception:
        pass  # Owner may not have started the bot in DM yet


def main() -> None:
    app = build_application()
    register_all_handlers(app)

    # Attach post_init
    app.post_init = post_init

    if cfg.WEBHOOK_URL:
        # ── Webhook mode ────────────────────────────────────────────────────
        logger.info("Starting in webhook mode: %s", cfg.WEBHOOK_URL)
        app.run_webhook(
            listen="0.0.0.0",
            port=cfg.WEBHOOK_PORT,
            webhook_url=cfg.WEBHOOK_URL,
            drop_pending_updates=True,
        )
    else:
        # ── Long polling mode ───────────────────────────────────────────────
        logger.info("Starting in polling mode…")
        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=[
                "message",
                "edited_message",
                "callback_query",
                "chat_member",
                "my_chat_member",
            ],
        )


if __name__ == "__main__":
    # Ensure data directory exists for SQLite
    os.makedirs("data", exist_ok=True)
    main()
