# 🤖 TGBot — Production Telegram Group Moderation Bot

A fully-featured, modular Telegram group moderation bot built with
`python-telegram-bot v21`, async SQLAlchemy, and SQLite (upgradeable to PostgreSQL).

---

## ✨ Feature Overview

| Category | Features |
|---|---|
| **Welcome** | Customizable greeting with `{mention}`, `{name}`, `{group}` variables |
| **Anti-Spam** | Flood detection, link blocking, forward blocking, content locks |
| **Moderation** | Mute, timed mute, kick, ban, timed ban, unban, warn system |
| **Warn System** | Warn → auto-action (mute/kick/ban) after configurable limit |
| **Locks** | Lock/unlock links, stickers, images, video, audio, documents, forwards |
| **Auto-Delete** | Command msgs, bot msgs, join/left msgs auto-deleted after 3s |
| **Edited Msgs** | Auto-delete edited messages after configurable delay (default 25s) |
| **Admin Tools** | Promote, demote, pin, unpin, adminlist |
| **Settings** | Interactive inline settings menu per group |
| **Logging** | Structured moderation logs to a dedicated channel/group |
| **Owner Panel** | Private DM help panel, admin access management by tier |
| **Custom Prefix** | Per-group prefix (default `.`) for all dot-commands |
| **Access Tiers** | full / limited / group_only / readonly for private panel access |

---

## 📁 Project Structure

```
tgbot/
├── main.py                    # Entry point
├── config.py                  # Environment config
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── Procfile                   # Railway / Render
├── .env.example
│
├── database/
│   ├── __init__.py
│   ├── engine.py              # Async SQLAlchemy engine
│   ├── models.py              # ORM models
│   └── repository.py         # All DB queries
│
├── handlers/
│   ├── __init__.py
│   ├── help.py                # /start /help with role-aware inline menus
│   ├── welcome.py             # New member welcome + service message cleanup
│   ├── antispam.py            # Flood / link / forward / lock enforcement
│   ├── moderation.py          # mute/kick/ban/warn/del + dot-command prefix router
│   ├── locks.py               # /lock /unlock /locks
│   ├── settings.py            # /settings inline menu + all /set* commands
│   ├── admin_tools.py         # /promote /demote /pin /adminlist
│   ├── owner.py               # /addadmin /removeadmin /adminpanel (owner only)
│   └── errors.py              # Global error handler
│
├── keyboards/
│   ├── __init__.py
│   └── menus.py               # All InlineKeyboardMarkup builders
│
├── middleware/
│   ├── __init__.py
│   └── permissions.py         # Role resolution (Owner/FullAdmin/LimitedAdmin/User)
│
├── services/
│   ├── __init__.py
│   ├── moderation_service.py  # mute/kick/ban/unban Telegram API calls
│   ├── spam_service.py        # In-memory flood & link detection
│   └── log_service.py         # Send structured logs to channel
│
└── utils/
    ├── __init__.py
    ├── helpers.py             # mention_html, safe_delete, auto_delete, is_admin
    ├── decorators.py          # @owner_only, @group_admin_only, @group_only
    └── time_parser.py         # parse_duration("10m") → 600
```

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.12+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- Your Telegram numeric user ID (get it from [@userinfobot](https://t.me/userinfobot))

### 1. Clone & Install

```bash
git clone https://github.com/yourname/tgbot.git
cd tgbot
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
nano .env                        # Fill in BOT_TOKEN and OWNER_ID
```

Required values in `.env`:
```
BOT_TOKEN=your_bot_token_here
OWNER_ID=123456789
```

### 3. Run

```bash
mkdir -p data
python main.py
```

The bot will initialise the SQLite database on first run and send you a startup
message in private chat.

---

## 🤖 BotFather Setup

In [@BotFather](https://t.me/BotFather):
1. Enable **group privacy mode OFF** (`/setprivacy` → Disable) so the bot can
   read all group messages.
2. Enable **Inline Mode** if you want button-based commands.
3. Set **Group Admin** permissions so the bot can mute, ban, delete messages.

When adding the bot to a group, grant it these admin rights:
- Delete messages
- Ban users
- Restrict members
- Pin messages (optional)
- Manage chat

---

## 📋 Command Reference

### Moderation (group admins)
| Command | Description |
|---|---|
| `.mute @user [reason]` | Mute user indefinitely |
| `.tmute @user 10m [reason]` | Timed mute (s/m/h/d) |
| `.unmute @user` | Remove mute |
| `.kick @user [reason]` | Kick user |
| `.ban @user [reason]` | Ban user |
| `.tban @user 2h [reason]` | Timed ban |
| `.unban @user` | Unban user |
| `.warn @user [reason]` | Add a warning |
| `.dwarn @user [reason]` | Warn + delete replied message |
| `.unwarn @user` | Remove one warning |
| `.resetwarn @user` | Reset all warnings |
| `.warns @user` | View warning count |
| `.del` | Delete replied message |

All dot-commands also work as slash-commands (e.g. `/mute`, `/tmute`).

### Anti-Spam (group admins)
```
/antispam on|off
/antilink on|off
/antiflood on|off
/floodrate <n>
/floodwindow <seconds>
```

### Locks (group admins)
```
/lock link|sticker|image|video|audio|document|forward
/unlock <type>
/locks
```

### Settings (group admins)
```
/settings            — Interactive inline menu
/setrules <text>
/setwelcome <text>   — Variables: {mention} {name} {group}
/setwarnlimit <n>
/setwarnaction mute|kick|ban
/setprefix <prefix>
/setlogchannel @channel
/setcmddelay <seconds>
/setediteddelay <seconds>
```

### Admin Tools (group admins)
```
/promote @user
/demote @user
/pin [silent]
/unpin
/adminlist
/rules
/stats @user
```

### Owner Tools (private chat only)
```
/addadmin @user full|limited|group_only|readonly
/removeadmin @user
/listadmins
/adminpanel
```

### Access Tiers
| Tier | Private Panel | Group Commands |
|---|---|---|
| `full` | ✅ Complete | ✅ All |
| `limited` | ⚠️ Limited | ✅ All |
| `group_only` | ❌ | ✅ All |
| `readonly` | ❌ Help only | ❌ |

---

## 🐳 Docker Deployment

```bash
# Build and run
docker compose up -d --build

# View logs
docker compose logs -f

# Stop
docker compose down
```

Data persists in `./data/tgbot.db` on the host.

---

## ☁️ Deploy to Railway

1. Push this repo to GitHub.
2. Create a new Railway project → **Deploy from GitHub repo**.
3. Add all `.env` variables in Railway's **Variables** tab.
4. Railway auto-detects the `Procfile` and runs `python main.py`.

For persistence on Railway, attach a **Volume** mounted at `/app/data`.

---

## ☁️ Deploy to Render

1. Create a new **Web Service** (or Background Worker).
2. Connect your GitHub repo.
3. Set **Start Command**: `python main.py`
4. Add environment variables from `.env`.
5. Attach a **Disk** at `/app/data` for database persistence.

---

## 🖥️ Deploy to VPS (systemd)

```bash
# Copy files to /opt/tgbot
sudo cp -r . /opt/tgbot
cd /opt/tgbot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env

# Create systemd service
sudo tee /etc/systemd/system/tgbot.service > /dev/null <<EOF
[Unit]
Description=Telegram Moderation Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/tgbot
ExecStart=/opt/tgbot/.venv/bin/python main.py
Restart=on-failure
RestartSec=5
EnvironmentFile=/opt/tgbot/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable tgbot
sudo systemctl start tgbot
sudo journalctl -fu tgbot
```

---

## 🗄️ Switch to PostgreSQL

1. Install the async driver: `pip install asyncpg`
2. Update `.env`:
   ```
   DATABASE_URL=postgresql+asyncpg://user:password@host:5432/tgbot
   ```
3. Remove the `connect_args` guard in `database/engine.py` (it's SQLite-only).
4. Restart. SQLAlchemy handles the rest.

---

## 🚀 Future Upgrade Ideas

- **Per-command enable/disable toggles** — let admins disable specific commands
- **Captcha on join** — CAPTCHA button challenge for new members
- **Scheduled messages** — cron-style announcements
- **Bad-words filter** — regex/word-list based auto-deletion
- **Report system** — `/report` for users to flag messages
- **Backup/restore** — export/import group settings as JSON
- **Multi-language support** — i18n with locale files per group
- **PostgreSQL + Redis** — for high-traffic groups (flood tracking in Redis)
- **Dashboard web UI** — FastAPI + React admin panel
- **Appeal system** — users DM the bot to appeal bans/mutes
- **Raid protection** — detect and auto-mute mass joins in short window
