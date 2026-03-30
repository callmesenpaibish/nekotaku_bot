# Telegram Moderation Bot

A production-ready, modular Telegram group moderation bot built with Python.

## Features
- **Moderation**: Mute, kick, ban (with timed variants), and a warning system with configurable auto-actions
- **Anti-Spam**: Flood detection, unauthorized link blocking, and forwarded message filtering
- **Customization**: Custom command prefixes, welcome messages, interactive settings menu
- **Logging**: Structured moderation logs sent to a dedicated Telegram channel
- **Access Control**: Multi-tiered permission system (Owner, Full Admin, Limited Admin, Group Admin, User)

## Tech Stack
- **Language**: Python 3.12
- **Framework**: python-telegram-bot v21.3 (async, Application/Builder pattern)
- **Database**: SQLite via SQLAlchemy 2.0 + aiosqlite (async)
- **Config**: python-dotenv for environment variable management

## Project Structure
```
main.py              # Entry point — builds and starts the bot
config.py            # Centralized config from environment variables
database/
  engine.py          # Async SQLAlchemy engine and session factory
  models.py          # ORM models (GroupSettings, UserWarning, ActionLog, etc.)
  repository.py      # CRUD database access layer
handlers/            # Telegram command/message handlers grouped by feature
  moderation.py      # Ban, kick, mute, warn commands
  antispam.py        # Flood, link, forward detection
  welcome.py         # Welcome/goodbye messages
  settings.py        # Interactive settings menu
  locks.py           # Message type locks
  admin_tools.py     # Admin utilities
  owner.py           # Owner-only commands
  help.py            # Help command
  errors.py          # Global error handler
services/            # Business logic (moderation_service, spam_service)
middleware/          # Permission resolution (permissions.py)
keyboards/           # Inline keyboard builders (menus.py)
utils/               # Decorators, time parsing, shared helpers
data/                # SQLite database file (auto-created at runtime)
```

## Required Environment Variables (Secrets)
- `BOT_TOKEN` — Telegram bot token from @BotFather
- `OWNER_ID` — Your Telegram user ID (numeric)

## Optional Environment Variables
- `TGBOT_DATABASE_URL` — Override the database URL (default: `sqlite+aiosqlite:///data/tgbot.db`)
- `BOT_USERNAME` — Bot username (auto-detected if not set)
- `LOG_CHANNEL_ID` — Telegram channel ID for moderation logs
- `WEBHOOK_URL` — Set to enable webhook mode instead of polling
- `WEBHOOK_PORT` — Port for webhook (default: 8443)
- `AUTO_DELETE_CMD_DELAY` — Seconds before deleting command messages (default: 3)
- `AUTO_DELETE_EDITED_DELAY` — Seconds before deleting edited messages (default: 25)
- `FLOOD_RATE` — Messages per window to trigger flood detection (default: 5)
- `FLOOD_WINDOW` — Flood detection window in seconds (default: 5)
- `SPAM_MUTE_DURATION` — Duration of spam mute in seconds (default: 600)

## Running the Bot
The bot runs in **long polling** mode by default. Set `WEBHOOK_URL` to switch to webhook mode.

The SQLite database is automatically created in the `data/` directory on first run.

## Notes
- `TGBOT_DATABASE_URL` is used instead of `DATABASE_URL` to avoid conflict with Replit's built-in PostgreSQL secret
- The bot sends a startup notification to the owner's DM when it comes online
