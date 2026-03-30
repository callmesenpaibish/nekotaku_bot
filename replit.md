# TGBot — Telegram Group Moderation Bot

## Overview
A production-ready, modular Telegram group moderation bot built with Python 3.12. Provides automated and manual tools for managing Telegram communities including anti-spam, welcome messages, user warns, and comprehensive moderation commands (mute, kick, ban).

## Tech Stack
- **Language**: Python 3.12
- **Framework**: python-telegram-bot v21.3 (async, polling mode)
- **Database**: PostgreSQL (Replit managed) via SQLAlchemy 2.0 + asyncpg
- **Config**: python-dotenv for environment variables

## Project Structure
```
main.py              — Entry point; builds app, registers handlers, starts polling
config.py            — Central config loaded from environment variables
requirements.txt     — Python dependencies
database/
  engine.py          — Async SQLAlchemy engine setup (handles URL normalization)
  models.py          — ORM models (GroupSettings, UserWarning, etc.)
  repository.py      — CRUD data access layer
handlers/            — Command handlers (moderation, antispam, welcome, etc.)
services/            — Business logic (spam detection, audit logging)
middleware/          — Permission checks and role resolution
keyboards/           — Inline menu definitions
utils/               — Helper functions and decorators
```

## Required Secrets
- `BOT_TOKEN` — Telegram bot token from @BotFather
- `OWNER_ID` — Telegram numeric user ID of the bot owner

## Environment Variables (Optional)
- `BOT_USERNAME` — Bot username without @
- `DATABASE_URL` — Auto-provided by Replit (PostgreSQL). Defaults to SQLite for local dev.
- `AUTO_DELETE_CMD_DELAY` — Seconds before deleting command messages (default: 3)
- `AUTO_DELETE_EDITED_DELAY` — Seconds before deleting edited messages (default: 25)
- `FLOOD_RATE` — Max messages per flood window (default: 5)
- `FLOOD_WINDOW` — Flood detection window in seconds (default: 5)
- `SPAM_MUTE_DURATION` — Auto-mute duration on spam in seconds (default: 600)
- `WEBHOOK_URL` — Set to enable webhook mode (leave empty for polling)
- `WEBHOOK_PORT` — Webhook port (default: 8443)
- `LOG_CHANNEL_ID` — Optional Telegram channel ID for action logs

## Running
The bot runs via the "Start application" workflow: `python main.py`

## Key Notes
- Uses long polling by default (no webhook URL needed in dev)
- `database/engine.py` handles PostgreSQL URL normalization (converts `postgresql://` → `postgresql+asyncpg://` and strips `sslmode` param for asyncpg compatibility)
- The bot notifies the owner on startup via Telegram DM
