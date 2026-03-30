"""config.py — Central configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Required environment variable '{key}' is not set.")
    return val


def _int(key: str, default: int) -> int:
    return int(os.getenv(key, default))


# ── Core ──────────────────────────────────────────────────────────────────────
BOT_TOKEN: str = _require("BOT_TOKEN")
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "")
OWNER_ID: int = int(_require("OWNER_ID"))

# ── Pyrogram ──────────────────────────────────────────────────────────────────
API_ID: int = int(_require("API_ID"))
API_HASH: str = _require("API_HASH")

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "TGBOT_DATABASE_URL", "sqlite+aiosqlite:///data/tgbot.db"
)

# ── Timings ───────────────────────────────────────────────────────────────────
AUTO_DELETE_CMD_DELAY: int = _int("AUTO_DELETE_CMD_DELAY", 3)
AUTO_DELETE_EDITED_DELAY: int = _int("AUTO_DELETE_EDITED_DELAY", 25)

# ── Anti-spam ─────────────────────────────────────────────────────────────────
FLOOD_RATE: int = _int("FLOOD_RATE", 5)
FLOOD_WINDOW: int = _int("FLOOD_WINDOW", 5)
SPAM_MUTE_DURATION: int = _int("SPAM_MUTE_DURATION", 600)

# ── Logging channel ───────────────────────────────────────────────────────────
LOG_CHANNEL_ID: int = int(os.getenv("LOG_CHANNEL_ID", 0)) or 0

# ── Command prefix ────────────────────────────────────────────────────────────
DEFAULT_PREFIX: str = "."

# ── Warn system ───────────────────────────────────────────────────────────────
DEFAULT_WARN_LIMIT: int = 3
DEFAULT_WARN_ACTION: str = "mute"

# ── Welcome ───────────────────────────────────────────────────────────────────
DEFAULT_WELCOME: str = (
    "👋 Welcome, {mention}! Please read the group rules with /rules."
)
