"""main.py — Entry point. Builds the Pyrogram Client and starts the bot."""

import asyncio
import logging
import os

from pyrogram import Client, idle
from pyrogram.enums import ParseMode

import config as cfg
from database.engine import init_db

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def build_client() -> Client:
    return Client(
        name="tgbot",
        api_id=cfg.API_ID,
        api_hash=cfg.API_HASH,
        bot_token=cfg.BOT_TOKEN,
        parse_mode=ParseMode.HTML,
        workdir="data",
    )


def register_all_handlers(app: Client) -> None:
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

    errors.register(app)
    help.register(app)
    welcome.register(app)
    owner.register(app)
    admin_tools.register(app)
    settings.register(app)
    locks.register(app)
    moderation.register(app)
    antispam.register(app)

    logger.info("All handlers registered.")


# ── Minimal health-check server (required for Render Web Service) ──────────────
async def _handle_health(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    await reader.read(1024)
    writer.write(
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/plain\r\n"
        b"Content-Length: 2\r\n"
        b"\r\n"
        b"OK"
    )
    await writer.drain()
    writer.close()


async def _start_health_server() -> None:
    port = int(os.getenv("PORT", 8080))
    server = await asyncio.start_server(_handle_health, "0.0.0.0", port)
    logger.info("Health-check server listening on port %d", port)
    async with server:
        await server.serve_forever()


async def main() -> None:
    os.makedirs("data", exist_ok=True)

    asyncio.create_task(_start_health_server())

    app = build_client()
    register_all_handlers(app)

    async with app:
        await init_db()
        logger.info("Database initialised.")

        me = await app.get_me()
        logger.info("Bot started: @%s (id=%d)", me.username, me.id)

        try:
            await app.send_message(
                chat_id=cfg.OWNER_ID,
                text=(
                    f"✅ <b>Bot online</b>\n"
                    f"Username: @{me.username}\n"
                    f"ID: <code>{me.id}</code>\n\n"
                    "Send /help to see available commands."
                ),
            )
        except Exception:
            pass

        await idle()


if __name__ == "__main__":
    asyncio.run(main())
