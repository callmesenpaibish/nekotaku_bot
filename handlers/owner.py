@owner_only
async def cmd_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /addadmin @user|user_id tier
    Or reply to a user: /addadmin tier
    """
    args = context.args
    reply = update.message.reply_to_message

    # 1. Determine target user and tier
    if reply:
        target_user = reply.from_user
        user_id = target_user.id
        username = target_user.username or target_user.first_name
        tier = args[0].lower() if args else None
    elif len(args) >= 2:
        identifier, tier = args[0], args[1].lower()
        user_id = None
        username = identifier
        
        # Try to parse ID or lookup username
        if identifier.lstrip("-").isdigit():
            user_id = int(identifier)
            try:
                chat = await context.bot.get_chat(user_id)
                username = getattr(chat, "username", None) or chat.first_name
            except Exception:
                # If get_chat fails but we have the ID, we can still proceed
                username = f"User:{user_id}"
        else:
            try:
                chat = await context.bot.get_chat(identifier)
                user_id = chat.id
                username = getattr(chat, "username", None) or identifier
            except Exception as e:
                await _reply(update, f"❌ <b>Chat not found.</b>\nTarget must start the bot first if using a username.\nError: {e}")
                return
    else:
        await _reply(update, "❌ <b>Usage:</b>\nReply to someone: <code>/addadmin full</code>\nOr: <code>/addadmin @user full</code>")
        return

    # 2. Validate Tier
    if tier not in VALID_TIERS:
        await _reply(update, f"❌ Invalid tier. Choose: {', '.join(VALID_TIERS)}")
        return

    # 3. Save to DB
    async with AsyncSessionLocal() as session:
        await add_allowed_admin(session, user_id=user_id, tier=tier, added_by=cfg.OWNER_ID)

    await _reply(
        update,
        f"✅ <b>{username}</b> added with tier <code>{tier}</code>.\n"
        f"<i>Note: If they haven't started the bot, they must do so to access the panel.</i>"
    )


@owner_only
async def cmd_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /removeadmin @user|user_id
    Or reply: /removeadmin
    """
    args = context.args
    reply = update.message.reply_to_message
    
    if reply:
        user_id = reply.from_user.id
    elif args:
        identifier = args[0]
        if identifier.lstrip("-").isdigit():
            user_id = int(identifier)
        else:
            try:
                chat = await context.bot.get_chat(identifier)
                user_id = chat.id
            except Exception:
                await _reply(update, "❌ Could not resolve username. Try using their User ID.")
                return
    else:
        await _reply(update, "❌ Usage: Reply to a user or provide <code>@username</code> / <code>user_id</code>")
        return

    async with AsyncSessionLocal() as session:
        removed = await remove_allowed_admin(session, user_id)

    if removed:
        await _reply(update, f"✅ User <code>{user_id}</code> removed from admins.")
    else:
        await _reply(update, f"❌ User <code>{user_id}</code> not found in admin list.")
