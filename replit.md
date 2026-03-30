# Telegram Moderation Bot

A production-ready, modular Telegram group moderation bot built with Python and Pyrogram.

## Features
- **Moderation**: Mute, kick, ban (with timed variants), and a warning system with configurable auto-actions
- **Anti-Spam**: Flood detection, unauthorized link blocking, and forwarded message filtering
- **Content Locks**: Lock/unlock specific content types (links, stickers, images, video, audio, documents, forwards)
- **Customization**: Custom command prefixes, welcome messages, interactive inline settings menu
- **Logging**: Structured moderation logs sent to a dedicated Telegram channel
- **Access Control**: Multi-tiered permission system (Owner, Full Admin, Limited Admin, Group Admin, User)

## Tech Stack
- **Language**: Python 3.12
- **Framework**: Pyrogram 2.0.106 (MTProto — much faster than HTTP polling)
- **Encryption**: TgCrypto (high-performance Pyrogram encryption)
- **Database**: SQLite via SQLAlchemy 2.0 + aiosqlite (async)
- **Config**: python-dotenv for environment variable management

## Project Structure
```
main.py              # Entry point — builds Pyrogram Client and starts the bot
config.py            # Centralised config from environment variables
data/
  tgbot.db           # SQLite database (auto-created at runtime)
  tgbot.session      # Pyrogram MTProto session file (auto-created)
database/
  engine.py          # Async SQLAlchemy engine and session factory
  models.py          # ORM models (GroupSettings, UserWarning, ActionLog, etc.)
  repository.py      # CRUD database access layer (with settings cache)
handlers/            # Telegram command/message handlers grouped by feature
  moderation.py      # Ban, kick, mute, warn commands + custom prefix routing
  antispam.py        # Flood, link, forward detection and command handlers
  welcome.py         # Welcome messages and service message cleanup
  settings.py        # Interactive inline settings menu + all /set* commands
  locks.py           # Content type lock/unlock commands
  admin_tools.py     # Promote, demote, pin, adminlist
  owner.py           # Owner-only admin management panel
  help.py            # /start and /help with inline help sections
  errors.py          # handle_errors() decorator for all handlers
services/
  moderation_service.py  # Core moderation actions (mute/kick/ban/unban)
  log_service.py         # Structured action logging to Telegram channel
  spam_service.py        # In-memory flood and duplicate detection (pure Python)
middleware/
  permissions.py     # Role resolution (Owner/FullAdmin/LimitedAdmin/User)
keyboards/
  menus.py           # Inline keyboard builders for all menus
utils/
  helpers.py         # mention_html, safe_delete, auto_delete, is_admin (cached)
  decorators.py      # @owner_only, @group_admin_only, @group_only
  time_parser.py     # Parse "10m", "2h" etc. to seconds and back
```

## Required Environment Variables (Secrets)
- `BOT_TOKEN` — Telegram bot token from @BotFather
- `OWNER_ID` — Your Telegram user ID (numeric)
- `API_ID` — Telegram app API ID from my.telegram.org
- `API_HASH` — Telegram app API hash from my.telegram.org

## Optional Environment Variables
- `TGBOT_DATABASE_URL` — Override DB URL (default: `sqlite+aiosqlite:///data/tgbot.db`)
- `LOG_CHANNEL_ID` — Telegram channel ID for moderation logs
- `AUTO_DELETE_CMD_DELAY` — Seconds before deleting command messages (default: 3)
- `AUTO_DELETE_EDITED_DELAY` — Seconds before deleting edited messages (default: 25)
- `FLOOD_RATE` — Messages per window to trigger flood detection (default: 5)
- `FLOOD_WINDOW` — Flood detection window in seconds (default: 5)
- `SPAM_MUTE_DURATION` — Duration of spam mute in seconds (default: 600)

## Running the Bot
The bot uses Pyrogram's MTProto protocol (no HTTP polling). Just run `python main.py`.
The SQLite database and session file are automatically created in the `data/` directory.

## Key Design Decisions
- **`TGBOT_DATABASE_URL`** instead of `DATABASE_URL` to avoid conflict with Replit's built-in PostgreSQL secret injection
- **Admin status cache** (5 min TTL) and **group settings cache** (60 sec TTL) eliminate per-message DB/API calls
- **`handle_errors` decorator** wraps every handler to catch RPCError/FloodWait without crashing
- **Pyrogram `workdir="data"`** keeps session files alongside the database
- Handler groups: antispam runs at group=5 (after commands), prefix handler at group=10 (lowest priority)
