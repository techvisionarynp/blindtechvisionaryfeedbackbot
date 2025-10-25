from fastapi import FastAPI, Request, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Dict, Optional
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "8439254355:AAF61_xtEU8EXfVjw8MfdMxghuCk5jyZhhw"
ADMIN_ID = 7026190306
WEBHOOK_URL = "https://blindtechvisionaryfeedbackbot.vercel.app/webhook"

# Store user information and conversation history
user_messages: Dict[int, dict] = {}
user_states: Dict[int, dict] = {}
conversation_map: Dict[int, int] = {}  # Maps admin message to user_id

# Initialize the bot application
ptb = (
    Application.builder()
    .updater(None)
    .token(TOKEN)
    .read_timeout(7)
    .get_updates_read_timeout(42)
    .build()
)

def get_user_keyboard():
    """Keyboard for regular users"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 Reply to Admin", callback_data="user_reply")],
        [InlineKeyboardButton("✉️ New Message", callback_data="user_new_message")]
    ])

def get_admin_keyboard(user_id: int):
    """Keyboard for admin to interact with user messages"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Reply to User", callback_data=f"admin_reply_{user_id}")],
        [InlineKeyboardButton("📢 Broadcast to All", callback_data="admin_send_all")]
    ])

def get_admin_main_keyboard():
    """Main keyboard for admin"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Send to All Users", callback_data="admin_send_all")]
    ])

def get_user_start_keyboard():
    """Start keyboard for new users"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✉️ Send Message", callback_data="user_new_message")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name or str(user_id)
    
    welcome_text = (
        "🤖 *Welcome to Blind Tech Visionary Feedback Bot*\n\n"
        "This bot is designed to collect feedback from you and send it to the admin "
        "of the Blind Tech Visionary community.\n\n"
        "You can send messages, and the admin will be able to reply to you directly."
    )
    
    # Register user if not already registered
    if user_id not in user_messages and user_id != ADMIN_ID:
        user_messages[user_id] = {
            "username": username,
            "user_id": user_id,
            "message_count": 0
        }
    
    # Clear any existing state
    user_states[user_id] = {}
    
    if user_id == ADMIN_ID:
        admin_text = (
            f"{welcome_text}\n\n"
            f"👑 *Admin Panel*\n"
            f"Total users: {len(user_messages)}\n\n"
            f"You can reply to user messages or broadcast to all users."
        )
        await update.message.reply_text(
            admin_text,
            reply_markup=get_admin_main_keyboard(),
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            welcome_text,
            reply_markup=get_user_start_keyboard(),
            parse_mode='Markdown'
        )

async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Forward user message to admin"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name or str(user_id)
    
    # Update user info
    if user_id not in user_messages:
        user_messages[user_id] = {
            "username": username,
            "user_id": user_id,
            "message_count": 0
        }
    
    user_messages[user_id]["message_count"] += 1
    user_messages[user_id]["last_message_id"] = update.message.message_id
    
    # Prepare caption
    user_info = f"👤 User: @{username} (ID: {user_id})\n"
    if update.message.caption:
        caption_text = f"{user_info}\n{update.message.caption}"
    else:
        caption_text = user_info.strip()
    
    admin_kb = get_admin_keyboard(user_id)
    
    try:
        sent_message = None
        
        if update.message.text:
            sent_message = await context.bot.send_message(
                ADMIN_ID,
                f"{user_info}\n💬 {update.message.text}",
                reply_markup=admin_kb
            )
        elif update.message.photo:
            sent_message = await context.bot.send_photo(
                ADMIN_ID,
                update.message.photo[-1].file_id,
                caption=caption_text,
                reply_markup=admin_kb
            )
        elif update.message.video:
            sent_message = await context.bot.send_video(
                ADMIN_ID,
                update.message.video.file_id,
                caption=caption_text,
                reply_markup=admin_kb
            )
        elif update.message.document:
            sent_message = await context.bot.send_document(
                ADMIN_ID,
                update.message.document.file_id,
                caption=caption_text,
                reply_markup=admin_kb
            )
        elif update.message.audio:
            sent_message = await context.bot.send_audio(
                ADMIN_ID,
                update.message.audio.file_id,
                caption=caption_text,
                reply_markup=admin_kb
            )
        elif update.message.voice:
            sent_message = await context.bot.send_voice(
                ADMIN_ID,
                update.message.voice.file_id,
                caption=caption_text,
                reply_markup=admin_kb
            )
        elif update.message.video_note:
            sent_message = await context.bot.send_video_note(
                ADMIN_ID,
                update.message.video_note.file_id,
                reply_markup=admin_kb
            )
            # Send user info separately for video notes (they don't support captions)
            await context.bot.send_message(
                ADMIN_ID,
                f"{user_info}(Video Note)",
                disable_notification=True
            )
        elif update.message.sticker:
            sent_message = await context.bot.send_sticker(
                ADMIN_ID,
                update.message.sticker.file_id,
                reply_markup=admin_kb
            )
            # Send user info separately for stickers
            await context.bot.send_message(
                ADMIN_ID,
                f"{user_info}(Sticker)",
                disable_notification=True
            )
        
        # Store the mapping for reply tracking
        if sent_message:
            conversation_map[sent_message.message_id] = user_id
            
        return True
        
    except Exception as e:
        logger.error(f"Error forwarding message to admin: {e}")
        return False

async def send_reply_to_user(target_user_id: int, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Send admin's reply to a specific user, handling different message types."""
    try:
        if update.message.text:
            await context.bot.send_message(
                target_user_id,
                f"💬 *Admin replied:*\n\n{update.message.text}",
                reply_markup=get_user_keyboard(),
                parse_mode='Markdown'
            )
        elif update.message.photo:
            caption = f"💬 *Admin replied:*\n\n{update.message.caption or ''}"
            await context.bot.send_photo(
                target_user_id,
                update.message.photo[-1].file_id,
                caption=caption,
                reply_markup=get_user_keyboard(),
                parse_mode='Markdown'
            )
        elif update.message.video:
            caption = f"💬 *Admin replied:*\n\n{update.message.caption or ''}"
            await context.bot.send_video(
                target_user_id,
                update.message.video.file_id,
                caption=caption,
                reply_markup=get_user_keyboard(),
                parse_mode='Markdown'
            )
        elif update.message.document:
            caption = f"💬 *Admin replied:*\n\n{update.message.caption or ''}"
            await context.bot.send_document(
                target_user_id,
                update.message.document.file_id,
                caption=caption,
                reply_markup=get_user_keyboard(),
                parse_mode='Markdown'
            )
        elif update.message.audio:
            caption = f"💬 *Admin replied:*\n\n{update.message.caption or ''}"
            await context.bot.send_audio(
                target_user_id,
                update.message.audio.file_id,
                caption=caption,
                reply_markup=get_user_keyboard(),
                parse_mode='Markdown'
            )
        elif update.message.voice:
            await context.bot.send_voice(
                target_user_id,
                update.message.voice.file_id,
                reply_markup=get_user_keyboard()
            )
        elif update.message.video_note:
            await context.bot.send_video_note(
                target_user_id,
                update.message.video_note.file_id,
                reply_markup=get_user_keyboard()
            )
        elif update.message.sticker:
            await context.bot.send_sticker(
                target_user_id,
                update.message.sticker.file_id,
                reply_markup=get_user_keyboard()
            )
        return True
    except Exception as e:
        logger.error(f"Failed to send reply to user {target_user_id}: {e}")
        return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all non-command messages"""
    user_id = update.effective_user.id
    state = user_states.get(user_id, {}).get("state")
    
    if user_id == ADMIN_ID:
        await handle_admin_message(update, context)
        return
    
    if state:
        await handle_user_state(update, context)
    else:
        # Forward message to admin
        success = await forward_to_admin(update, context)
        if success:
            await update.message.reply_text(
                "✅ Your message has been sent to the admin successfully!",
                reply_markup=get_user_keyboard()
            )
        else:
            await update.message.reply_text(
                "❌ Failed to send message. Please try again later.",
                reply_markup=get_user_keyboard()
            )

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages from admin"""
    state = user_states.get(ADMIN_ID, {}).get("state")
    
    if state == "waiting_broadcast":
        # Broadcast message to all users
        message_sent_count = 0
        message_failed_count = 0
        
        for uid in user_messages.keys():
            if await send_reply_to_user(uid, update, context):  # Reuse send function, but it's reply, but for broadcast, adjust if needed
                message_sent_count += 1
            else:
                message_failed_count += 1
        
        await update.message.reply_text(
            f"📊 *Broadcast Results:*\n"
            f"✅ Sent: {message_sent_count}\n"
            f"❌ Failed: {message_failed_count}",
            reply_markup=get_admin_main_keyboard(),
            parse_mode='Markdown'
        )
        user_states[ADMIN_ID] = {}
        
    elif state == "waiting_admin_reply":
        # Reply to specific user
        target_user_id = user_states[ADMIN_ID].get("target_user_id")
        
        if not target_user_id:
            await update.message.reply_text(
                "❌ Error: No target user found. Please try again.",
                reply_markup=get_admin_main_keyboard()
            )
            user_states[ADMIN_ID] = {}
            return
        
        if target_user_id not in user_messages:
            await update.message.reply_text(
                "❌ Error: User not found in the system.",
                reply_markup=get_admin_main_keyboard()
            )
            user_states[ADMIN_ID] = {}
            return
        
        success = await send_reply_to_user(target_user_id, update, context)
        username = user_messages[target_user_id].get("username", "Unknown")
        if success:
            await update.message.reply_text(
                f"✅ Reply sent successfully to @{username}",
                reply_markup=get_admin_main_keyboard()
            )
        else:
            await update.message.reply_text(
                "❌ Failed to send reply. The user might have blocked the bot.",
                reply_markup=get_admin_main_keyboard()
            )
        
        user_states[ADMIN_ID] = {}
    else:
        # Check if replying to a forwarded message
        if update.message.reply_to_message and update.message.reply_to_message.message_id in conversation_map:
            target_user_id = conversation_map[update.message.reply_to_message.message_id]
            if target_user_id not in user_messages:
                await update.message.reply_text(
                    "❌ Error: User not found in the system.",
                    reply_markup=get_admin_main_keyboard()
                )
                return
            
            success = await send_reply_to_user(target_user_id, update, context)
            username = user_messages[target_user_id].get("username", "Unknown")
            if success:
                await update.message.reply_text(
                    f"✅ Reply sent successfully to @{username}",
                    reply_markup=get_admin_main_keyboard()
                )
            else:
                await update.message.reply_text(
                    "❌ Failed to send reply. The user might have blocked the bot.",
                    reply_markup=get_admin_main_keyboard()
                )
        else:
            # Admin sent a message without any state or reply
            await update.message.reply_text(
                "ℹ️ Please use the buttons to reply to users or broadcast messages, or reply directly to user messages.",
                reply_markup=get_admin_main_keyboard()
            )

async def handle_user_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages when in a specific state"""
    user_id = update.effective_user.id
    state = user_states.get(user_id, {}).get("state")
    
    if state in ["waiting_new_message", "waiting_reply"]:
        success = await forward_to_admin(update, context)
        
        if success:
            if state == "waiting_new_message":
                await update.message.reply_text(
                    "✅ Your message has been sent to the admin!",
                    reply_markup=get_user_keyboard()
                )
            else:
                await update.message.reply_text(
                    "✅ Your reply has been sent to the admin!",
                    reply_markup=get_user_keyboard()
                )
        else:
            await update.message.reply_text(
                "❌ Failed to send message. Please try again.",
                reply_markup=get_user_keyboard()
            )
        
        user_states[user_id] = {}

async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reply command"""
    user_id = update.effective_user.id
    
    if user_id == ADMIN_ID:
        # Admin wants to reply using command
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "ℹ️ *Usage:* `/reply @username your message here`\n\n"
                "Or use the reply buttons on user messages.",
                parse_mode='Markdown'
            )
            return
        
        target_username = context.args[0].replace("@", "")
        reply_text = " ".join(context.args[1:])
        
        # Find user by username
        target_user_id = None
        for uid, data in user_messages.items():
            if data["username"].replace("@", "").lower() == target_username.lower():
                target_user_id = uid
                break
        
        if not target_user_id:
            await update.message.reply_text(
                f"❌ User @{target_username} not found.\n\n"
                "Make sure the user has sent at least one message to the bot.",
                reply_markup=get_admin_main_keyboard()
            )
            return
        
        # Create a dummy update for text message
        dummy_message = Update(message_id=0, message={
            "text": reply_text,
            "chat": {"id": ADMIN_ID}
        }, effective_user={"id": ADMIN_ID})  # Hacky, but since send_reply_to_user uses update.message.text
        dummy_update = update  # Wait, better to send directly
        try:
            await context.bot.send_message(
                target_user_id,
                f"💬 *Admin replied:*\n\n{reply_text}",
                reply_markup=get_user_keyboard(),
                parse_mode='Markdown'
            )
            await update.message.reply_text(
                f"✅ Reply sent to @{target_username}",
                reply_markup=get_admin_main_keyboard()
            )
        except Exception as e:
            logger.error(f"Failed to send reply via command: {e}")
            await update.message.reply_text(
                "❌ Failed to send reply. The user might have blocked the bot.",
                reply_markup=get_admin_main_keyboard()
            )
    else:
        # Regular user wants to reply to admin
        if not user_messages.get(user_id, {}).get("message_count", 0):
            await update.message.reply_text(
                "ℹ️ You haven't sent any messages yet. Send a message first!",
                reply_markup=get_user_start_keyboard()
            )
            return
        
        user_states[user_id] = {"state": "waiting_reply"}
        await update.message.reply_text(
            "✍️ Write your reply to the admin:"
        )

async def sendnewmessage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sendnewmessage command"""
    user_id = update.effective_user.id
    
    if user_id == ADMIN_ID:
        await update.message.reply_text(
            "ℹ️ Admins should use /sendmessagetoall for broadcasts.",
            reply_markup=get_admin_main_keyboard()
        )
        return
    
    user_states[user_id] = {"state": "waiting_new_message"}
    await update.message.reply_text(
        "✍️ Write your message for the admin:"
    )

async def sendmessagetoall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sendmessagetoall command (admin only)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is only for administrators.")
        return
    
    if not user_messages:
        await update.message.reply_text(
            "ℹ️ No users in the database yet. Wait for users to send messages first.",
            reply_markup=get_admin_main_keyboard()
        )
        return
    
    user_states[ADMIN_ID] = {"state": "waiting_broadcast"}
    await update.message.reply_text(
        f"✍️ Write your message to broadcast to all {len(user_messages)} users:"
    )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command"""
    user_id = update.effective_user.id
    
    if user_id in user_states:
        user_states[user_id] = {}
    
    if user_id == ADMIN_ID:
        await update.message.reply_text(
            "✅ Action cancelled.",
            reply_markup=get_admin_main_keyboard()
        )
    else:
        await update.message.reply_text(
            "✅ Action cancelled.",
            reply_markup=get_user_keyboard()
        )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command (admin only)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is only for administrators.")
        return
    
    total_users = len(user_messages)
    total_messages = sum(data.get("message_count", 0) for data in user_messages.values())
    
    stats_text = (
        f"📊 *Bot Statistics*\n\n"
        f"👥 Total Users: {total_users}\n"
        f"💬 Total Messages: {total_messages}\n\n"
    )
    
    if total_users > 0:
        stats_text += "*Recent Users:*\n"
        # Show last 5 users
        recent_users = list(user_messages.items())[-5:]
        for uid, data in recent_users:
            username = data.get("username", "Unknown")
            msg_count = data.get("message_count", 0)
            stats_text += f"• @{username}: {msg_count} messages\n"
    else:
        stats_text += "No users yet."
    
    await update.message.reply_text(
        stats_text,
        reply_markup=get_admin_main_keyboard(),
        parse_mode='Markdown'
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "user_new_message":
        user_states[user_id] = {"state": "waiting_new_message"}
        await query.message.reply_text("✍️ Write your message for the admin:")
    
    elif data == "user_reply":
        if not user_messages.get(user_id, {}).get("message_count", 0) and user_id != ADMIN_ID:
            await query.message.reply_text(
                "ℹ️ You haven't sent any messages yet. Send a message first!",
                reply_markup=get_user_start_keyboard()
            )
            return
        
        user_states[user_id] = {"state": "waiting_reply"}
        await query.message.reply_text("✍️ Write your reply for the admin:")
    
    elif data.startswith("admin_reply_"):
        try:
            target_user_id = int(data.split("_")[2])
            
            if target_user_id not in user_messages:
                await query.message.reply_text(
                    "❌ User not found in the system.",
                    reply_markup=get_admin_main_keyboard()
                )
                return
            
            user_states[ADMIN_ID] = {
                "state": "waiting_admin_reply",
                "target_user_id": target_user_id
            }
            
            username = user_messages[target_user_id].get("username", "Unknown")
            await query.message.reply_text(
                f"✍️ Write your reply for @{username}:"
            )
        except (IndexError, ValueError) as e:
            logger.error(f"Error parsing callback data: {e}")
            await query.message.reply_text(
                "❌ Invalid callback data.",
                reply_markup=get_admin_main_keyboard()
            )
    
    elif data == "admin_send_all":
        if user_id != ADMIN_ID:
            await query.answer("❌ Admin only!", show_alert=True)
            return
        
        if not user_messages:
            await query.message.reply_text(
                "ℹ️ No users in the database yet.",
                reply_markup=get_admin_main_keyboard()
            )
            return
        
        user_states[ADMIN_ID] = {"state": "waiting_broadcast"}
        await query.message.reply_text(
            f"✍️ Write your message to broadcast to all {len(user_messages)} users:"
        )

# Add handlers
ptb.add_handler(CommandHandler("start", start))
ptb.add_handler(CommandHandler("reply", reply_command))
ptb.add_handler(CommandHandler("sendnewmessage", sendnewmessage_command))
ptb.add_handler(CommandHandler("sendmessagetoall", sendmessagetoall_command))
ptb.add_handler(CommandHandler("cancel", cancel_command))
ptb.add_handler(CommandHandler("stats", stats_command))
ptb.add_handler(CallbackQueryHandler(button_callback))
ptb.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Manage application lifespan"""
    logger.info("Starting bot...")
    
    # Initialize the bot
    await ptb.initialize()
    
    # Set webhook
    webhook_info = await ptb.bot.get_webhook_info()
    if webhook_info.url != WEBHOOK_URL:
        await ptb.bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook set to: {WEBHOOK_URL}")
    else:
        logger.info(f"Webhook already set to: {WEBHOOK_URL}")
    
    # Set bot commands
    commands = [
        ("start", "Start the bot"),
        ("reply", "Reply to admin/user"),
        ("sendnewmessage", "Send new message to admin"),
        ("sendmessagetoall", "Broadcast to all users (admin)"),
        ("cancel", "Cancel current action"),
        ("stats", "View bot statistics (admin)")
    ]
    await ptb.bot.set_my_commands(commands)
    logger.info("Bot commands set")
    
    yield
    
    # Cleanup
    logger.info("Shutting down bot...")
    await ptb.bot.delete_webhook()
    await ptb.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def webhook_post(request: Request):
    """Handle incoming webhook updates (POST)"""
    try:
        data = await request.json()
        update = Update.de_json(data, ptb.bot)
        await ptb.process_update(update)
        return Response(status_code=HTTPStatus.OK)
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return Response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

@app.get("/webhook")
async def webhook_get():
    """Handle GET requests to webhook (health check)"""
    return {"status": "ok", "message": "Webhook is active"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "status": "running",
        "bot": "Blind Tech Visionary Feedback Bot",
        "users": len(user_messages)
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        bot_info = await ptb.bot.get_me()
        webhook_info = await ptb.bot.get_webhook_info()
        return {
            "status": "healthy",
            "bot_username": bot_info.username,
            "webhook_url": webhook_info.url,
            "pending_updates": webhook_info.pending_update_count
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@app.get("/set_webhook")
async def set_webhook_route():
    """Manually set webhook"""
    try:
        await ptb.bot.set_webhook(url=WEBHOOK_URL)
        info = await ptb.bot.get_webhook_info()
        return {
            "success": True,
            "webhook_url": WEBHOOK_URL,
            "webhook_info": {
                "url": info.url,
                "has_custom_certificate": info.has_custom_certificate,
                "pending_update_count": info.pending_update_count,
                "last_error_message": info.last_error_message
            }
        }
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        return {
            "success": False,
            "error": str(e)
        }