"""handlers/admin_tools.py — Promote, demote, pin, adminlist, editrights, settitle."""

import asyncio
from pyrogram import Client, filters, raw
from pyrogram.types import Message, CallbackQuery, ChatPrivileges, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMembersFilter, ChatMemberStatus
from pyrogram.errors import RPCError
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

from utils.decorators import group_admin_only, group_only
from utils.helpers import auto_delete, mention_html, safe_delete
from handlers.errors import handle_errors
import config as cfg


# ─── Rights bit map ───────────────────────────────────────────────────────────
# Each bit position maps to one ChatPrivileges field
_RIGHTS = [
    ("can_manage_chat",        "🔧 Manage Chat"),
    ("can_delete_messages",    "🗑 Delete Messages"),
    ("can_restrict_members",   "🚫 Restrict Members"),
    ("can_promote_members",    "⭐ Add Admins"),
    ("can_change_info",        "ℹ️ Change Info"),
    ("can_invite_users",       "🔗 Invite Users"),
    ("can_pin_messages",       "📌 Pin Messages"),
    ("can_manage_video_chats", "📹 Video Chats"),
]

# Default bitmask: all rights ON except "Add Admins" (bit 3) and "Change Info" (bit 4)
_DEFAULT_MASK = 0b11100111  # 231


def _mask_to_privileges(mask: int) -> ChatPrivileges:
    kwargs = {field: bool(mask & (1 << i)) for i, (field, _) in enumerate(_RIGHTS)}
    return ChatPrivileges(**kwargs)


def _privileges_to_mask(p: ChatPrivileges) -> int:
    mask = 0
    for i, (field, _) in enumerate(_RIGHTS):
        if getattr(p, field, False):
            mask |= (1 << i)
    return mask


def _rights_keyboard(prefix: str, chat_id: int, user_id: int, mask: int, confirm_text: str) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(_RIGHTS), 2):
        row = []
        for bit in range(i, min(i + 2, len(_RIGHTS))):
            _, label = _RIGHTS[bit]
            status = "✅" if (mask & (1 << bit)) else "❌"
            row.append(InlineKeyboardButton(
                f"{status} {label}",
                callback_data=f"{prefix}:{chat_id}:{user_id}:{mask}:t{bit}",
            ))
        rows.append(row)
    rows.append([
        InlineKeyboardButton(f"✔ {confirm_text}", callback_data=f"{prefix}:{chat_id}:{user_id}:{mask}:go"),
        InlineKeyboardButton("✖ Cancel",           callback_data=f"{prefix}:{chat_id}:{user_id}:{mask}:cancel"),
    ])
    return InlineKeyboardMarkup(rows)


async def _reply_auto(message: Message, text: str, delay: int = 6) -> None:
    msg = await message.reply(text)
    asyncio.create_task(auto_delete(msg, delay))
    asyncio.create_task(auto_delete(message, 3))


async def _resolve_target(client: Client, message: Message, args: list):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    if args:
        identifier = args[0]
        try:
            uid = int(identifier) if identifier.lstrip("-").isdigit() else identifier
            member = await client.get_chat_member(message.chat.id, uid)
            return member.user
        except RPCError:
            await message.reply("❌ User not found.")
            return None
    await message.reply("❌ Reply to a user or specify @username / user ID.")
    return None


# ─── /promote — show rights selector ─────────────────────────────────────────
@handle_errors
@group_admin_only
@group_only
async def cmd_promote(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    target = await _resolve_target(client, message, args)
    if not target:
        return
    if target.id == cfg.OWNER_ID:
        await _reply_auto(message, "⛔ Cannot promote the bot owner via this command.")
        return
    if target.is_bot:
        await _reply_auto(message, "⛔ Cannot promote bots via this command.")
        return

    kb = _rights_keyboard("promo", message.chat.id, target.id, _DEFAULT_MASK, "Promote")
    msg = await message.reply(
        f"⭐ <b>Promote {mention_html(target)}</b>\n\n"
        "Toggle the rights you want to grant, then press <b>Promote</b>.",
        reply_markup=kb,
    )
    asyncio.create_task(auto_delete(message, 3))
    asyncio.create_task(auto_delete(msg, 90))


# ─── promote callback ─────────────────────────────────────────────────────────
@handle_errors
async def promote_callback(client: Client, cq: CallbackQuery) -> None:
    _, chat_id_s, user_id_s, mask_s, action = cq.data.split(":")
    chat_id = int(chat_id_s)
    user_id = int(user_id_s)
    mask = int(mask_s)

    invoker_member = await client.get_chat_member(chat_id, cq.from_user.id)
    if invoker_member.status not in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
        await cq.answer("⛔ Admins only.", show_alert=True)
        return
    if invoker_member.status == ChatMemberStatus.ADMINISTRATOR and not invoker_member.privileges.can_promote_members:
        await cq.answer("⛔ You don't have permission to add admins.", show_alert=True)
        return

    if action == "cancel":
        await cq.message.delete()
        await cq.answer("Cancelled.")
        return

    if action == "go":
        try:
            target_user = await client.get_users(user_id)
            await client.promote_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                privileges=_mask_to_privileges(mask),
            )
            await cq.message.edit_text(f"✅ {mention_html(target_user)} has been promoted.")
            await cq.answer("Promoted!")
        except RPCError as e:
            await cq.answer(f"❌ Failed: {e}", show_alert=True)
        return

    # Toggle bit
    bit = int(action[1:])
    mask ^= (1 << bit)
    kb = _rights_keyboard("promo", chat_id, user_id, mask, "Promote")
    await cq.message.edit_reply_markup(kb)
    await cq.answer()


# ─── /editrights — edit an existing admin's rights ────────────────────────────
@handle_errors
@group_admin_only
@group_only
async def cmd_editrights(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    target = await _resolve_target(client, message, args)
    if not target:
        return

    try:
        member = await client.get_chat_member(message.chat.id, target.id)
    except RPCError as e:
        await _reply_auto(message, f"❌ Could not fetch member: {e}")
        return

    if member.status not in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
        await _reply_auto(message, "❌ That user is not an admin.")
        return
    if member.status == ChatMemberStatus.OWNER:
        await _reply_auto(message, "⛔ Cannot edit the group owner's rights.")
        return

    mask = _privileges_to_mask(member.privileges) if member.privileges else _DEFAULT_MASK
    kb = _rights_keyboard("erght", message.chat.id, target.id, mask, "Save Rights")
    msg = await message.reply(
        f"✏️ <b>Edit rights for {mention_html(target)}</b>\n\n"
        "Toggle rights, then press <b>Save Rights</b>.",
        reply_markup=kb,
    )
    asyncio.create_task(auto_delete(message, 3))
    asyncio.create_task(auto_delete(msg, 90))


# ─── editrights callback ──────────────────────────────────────────────────────
@handle_errors
async def editrights_callback(client: Client, cq: CallbackQuery) -> None:
    _, chat_id_s, user_id_s, mask_s, action = cq.data.split(":")
    chat_id = int(chat_id_s)
    user_id = int(user_id_s)
    mask = int(mask_s)

    invoker_member = await client.get_chat_member(chat_id, cq.from_user.id)
    if invoker_member.status not in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
        await cq.answer("⛔ Admins only.", show_alert=True)
        return
    if invoker_member.status == ChatMemberStatus.ADMINISTRATOR and not invoker_member.privileges.can_promote_members:
        await cq.answer("⛔ You need 'Add Admins' right to edit admin rights.", show_alert=True)
        return

    if action == "cancel":
        await cq.message.delete()
        await cq.answer("Cancelled.")
        return

    if action == "go":
        try:
            target_user = await client.get_users(user_id)
            await client.promote_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                privileges=_mask_to_privileges(mask),
            )
            await cq.message.edit_text(f"✅ Rights updated for {mention_html(target_user)}.")
            await cq.answer("Saved!")
        except RPCError as e:
            await cq.answer(f"❌ Failed: {e}", show_alert=True)
        return

    bit = int(action[1:])
    mask ^= (1 << bit)
    kb = _rights_keyboard("erght", chat_id, user_id, mask, "Save Rights")
    await cq.message.edit_reply_markup(kb)
    await cq.answer()


# ─── /settitle — set custom admin title/tag ───────────────────────────────────
@handle_errors
@group_admin_only
@group_only
async def cmd_settitle(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    if not args:
        await _reply_auto(message, "❌ Usage: /settitle @user <title>\nExample: /settitle @john Helper")
        return

    target = await _resolve_target(client, message, args)
    if not target:
        return

    if message.reply_to_message:
        title_args = args
    else:
        title_args = args[1:]

    title = " ".join(title_args).strip()
    if not title:
        await _reply_auto(message, "❌ Please provide a title. Example: /settitle @user Helper")
        return
    if len(title) > 16:
        await _reply_auto(message, "❌ Title must be 16 characters or fewer.")
        return

    try:
        member = await client.get_chat_member(message.chat.id, target.id)
        if member.status not in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
            await _reply_auto(message, "❌ That user is not an admin — promote them first.")
            return
        if member.status == ChatMemberStatus.OWNER:
            await _reply_auto(message, "⛔ Cannot change the group owner's title.")
            return

        p = member.privileges
        await client.invoke(
            raw.functions.channels.EditAdmin(
                channel=await client.resolve_peer(message.chat.id),
                user_id=await client.resolve_peer(target.id),
                admin_rights=raw.types.ChatAdminRights(
                    change_info=bool(p and p.can_change_info),
                    post_messages=False,
                    edit_messages=False,
                    delete_messages=bool(p and p.can_delete_messages),
                    ban_users=bool(p and p.can_restrict_members),
                    invite_users=bool(p and p.can_invite_users),
                    pin_messages=bool(p and p.can_pin_messages),
                    add_admins=bool(p and p.can_promote_members),
                    anonymous=False,
                    manage_call=bool(p and p.can_manage_video_chats),
                    other=bool(p and p.can_manage_chat),
                    manage_topics=False,
                ),
                rank=title,
            )
        )
        await _reply_auto(message, f"✅ Title for {mention_html(target)} set to <b>{title}</b>.")
    except RPCError as e:
        await _reply_auto(message, f"❌ Failed to set title: {e}")


# ─── /demote ──────────────────────────────────────────────────────────────────
@handle_errors
@group_admin_only
@group_only
async def cmd_demote(client: Client, message: Message) -> None:
    args = message.command[1:] if message.command else []
    target = await _resolve_target(client, message, args)
    if not target:
        return
    try:
        await client.promote_chat_member(
            chat_id=message.chat.id,
            user_id=target.id,
            privileges=ChatPrivileges(
                can_manage_chat=False,
                can_delete_messages=False,
                can_restrict_members=False,
                can_invite_users=False,
                can_pin_messages=False,
            ),
        )
        await _reply_auto(message, f"⬇️ {mention_html(target)} has been demoted.")
    except RPCError as e:
        await _reply_auto(message, f"❌ Failed to demote: {e}")


# ─── /pin / /unpin ────────────────────────────────────────────────────────────
@handle_errors
@group_admin_only
@group_only
async def cmd_pin(client: Client, message: Message) -> None:
    if not message.reply_to_message:
        await _reply_auto(message, "❌ Reply to a message to pin it.")
        return
    args = message.command[1:] if message.command else []
    silent = bool(args and args[0].lower() == "silent")
    try:
        await client.pin_chat_message(
            chat_id=message.chat.id,
            message_id=message.reply_to_message.id,
            disable_notification=silent,
        )
        await _reply_auto(message, "📌 Message pinned." + (" (silent)" if silent else ""))
    except RPCError as e:
        await _reply_auto(message, f"❌ Could not pin: {e}")


@handle_errors
@group_admin_only
@group_only
async def cmd_unpin(client: Client, message: Message) -> None:
    try:
        await client.unpin_chat_message(chat_id=message.chat.id)
        await _reply_auto(message, "📌 Message unpinned.")
    except RPCError as e:
        await _reply_auto(message, f"❌ Could not unpin: {e}")


# ─── /adminlist ───────────────────────────────────────────────────────────────
@handle_errors
@group_admin_only
@group_only
async def cmd_adminlist(client: Client, message: Message) -> None:
    try:
        lines = ["👮 <b>Group Admins</b>\n"]
        async for admin in client.get_chat_members(message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS):
            user = admin.user
            if user.is_bot:
                continue
            title = getattr(admin, "custom_title", None) or admin.status.name.capitalize()
            lines.append(f"• {mention_html(user)} — <i>{title}</i>")
        msg = await message.reply("\n".join(lines))
        asyncio.create_task(auto_delete(msg, 15))
        asyncio.create_task(auto_delete(message, 3))
    except RPCError as e:
        await _reply_auto(message, f"❌ Error: {e}")


# ─── Register ─────────────────────────────────────────────────────────────────
def register(app: Client) -> None:
    app.add_handler(MessageHandler(cmd_promote,     filters.command("promote")     & filters.group))
    app.add_handler(MessageHandler(cmd_demote,      filters.command("demote")      & filters.group))
    app.add_handler(MessageHandler(cmd_editrights,  filters.command("editrights")  & filters.group))
    app.add_handler(MessageHandler(cmd_settitle,    filters.command("settitle")    & filters.group))
    app.add_handler(MessageHandler(cmd_pin,         filters.command("pin")         & filters.group))
    app.add_handler(MessageHandler(cmd_unpin,       filters.command("unpin")       & filters.group))
    app.add_handler(MessageHandler(cmd_adminlist,   filters.command("adminlist")   & filters.group))
    app.add_handler(CallbackQueryHandler(promote_callback,    filters.regex(r"^promo:")))
    app.add_handler(CallbackQueryHandler(editrights_callback, filters.regex(r"^erght:")))
