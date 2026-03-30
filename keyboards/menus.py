"""keyboards/menus.py — Inline keyboard builders for all menus."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ── Help main menu ────────────────────────────────────────────────────────────

def help_main_menu(is_owner: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("🔨 Moderation", callback_data="help:mod"),
            InlineKeyboardButton("🛡 Anti-Spam",  callback_data="help:spam"),
        ],
        [
            InlineKeyboardButton("🔒 Locks",        callback_data="help:locks"),
            InlineKeyboardButton("⚠️ Warnings",     callback_data="help:warn"),
        ],
        [
            InlineKeyboardButton("⚙️ Group Settings", callback_data="help:settings"),
            InlineKeyboardButton("👮 Admin Tools",    callback_data="help:admin"),
        ],
    ]
    if is_owner:
        buttons.append([
            InlineKeyboardButton("👑 Owner Tools", callback_data="help:owner"),
        ])
    return InlineKeyboardMarkup(buttons)


def help_back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("« Back", callback_data="help:main")]
    ])


# ── Settings menu ─────────────────────────────────────────────────────────────

def settings_menu(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👋 Welcome",     callback_data=f"cfg:{chat_id}:welcome"),
            InlineKeyboardButton("🛡 Anti-Spam",   callback_data=f"cfg:{chat_id}:antispam"),
        ],
        [
            InlineKeyboardButton("🔗 Anti-Link",   callback_data=f"cfg:{chat_id}:antilink"),
            InlineKeyboardButton("🌊 Anti-Flood",  callback_data=f"cfg:{chat_id}:flood"),
        ],
        [
            InlineKeyboardButton("⚠️ Warn Limit",  callback_data=f"cfg:{chat_id}:warnlimit"),
            InlineKeyboardButton("🔒 Locks",        callback_data=f"cfg:{chat_id}:locks"),
        ],
        [
            InlineKeyboardButton("📋 Logging",     callback_data=f"cfg:{chat_id}:logging"),
            InlineKeyboardButton("🗑 Auto-Delete",  callback_data=f"cfg:{chat_id}:autodelete"),
        ],
        [InlineKeyboardButton("« Close", callback_data="cfg:close")],
    ])


def toggle_button(label: str, enabled: bool, callback: str) -> InlineKeyboardButton:
    icon = "✅" if enabled else "❌"
    return InlineKeyboardButton(f"{icon} {label}", callback_data=callback)


def setting_back(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("« Settings", callback_data=f"cfg:{chat_id}:main")]
    ])


# ── Admin panel (owner private chat) ─────────────────────────────────────────

def admin_panel_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add Admin",    callback_data="oadmin:add"),
            InlineKeyboardButton("➖ Remove Admin", callback_data="oadmin:remove"),
        ],
        [
            InlineKeyboardButton("📋 List Admins",  callback_data="oadmin:list"),
        ],
        [InlineKeyboardButton("« Close", callback_data="oadmin:close")],
    ])
