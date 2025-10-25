from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Dict
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "8439254355:AAF61_xtEU8EXfVjw8MfdMxghuCk5jyZhhw"
ADMIN_ID = 7026190306
WEBHOOK_URL = "https://blindtechvisionaryfeedbackbot.vercel.app/webhook"

user_messages: Dict[int, dict] = {}
user_states: Dict[int, dict] = {}

ptb = (
    Application.builder()
    .updater(None)
    .token(TOKEN)
    .read_timeout(7)
    .get_updates_read_timeout(42)
    .build()
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name or str(user_id)
    
    if user_id == ADMIN_ID:
        await update.message.reply_text("Admin, I will forward you the user's message to you.")
    else:
        if user_id not in user_messages:
            user_messages[user_id] = {"username": username}
        await update.message.reply_text(f"Hey {username}, Write your feedback to the admins. I will forward.")

async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_messages:
        username = update.effective_user.username or update.effective_user.first_name or str(user_id)
        user_messages[user_id] = {"username": username}
    else:
        username = user_messages[user_id]["username"]
    
    message = update.message.text
    
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"@{username} said, {message}"
        )
        return True
    except Exception as e:
        logger.error(f"Error forwarding message to admin: {e}")
        return False

async def send_to_user(target_user_id: int, text: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        await context.bot.send_message(
            target_user_id,
            text
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send message to user {target_user_id}: {e}")
        return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id == ADMIN_ID:
        state = user_states.get(ADMIN_ID, {}).get("state")
        
        if state == "waiting_broadcast":
            message = update.message.text
            sent_count = 0
            failed_count = 0
            
            for uid in list(user_messages.keys()):
                if await send_to_user(uid, message, context):
                    sent_count += 1
                else:
                    failed_count += 1
            
            await update.message.reply_text(
                f"I forwarded your message to all users.\n✅ Sent: {sent_count}\n❌ Failed: {failed_count}"
            )
            if ADMIN_ID in user_states:
                del user_states[ADMIN_ID]
        else:
            await update.message.reply_text(
                "Use commands like /informusers or /senduser to interact."
            )
    else:
        success = await forward_to_admin(update, context)
        if success:
            await update.message.reply_text(
                "Successfully, I forwarded your message to the admin. you can continue sending me messages. I will forward."
            )
        else:
            await update.message.reply_text(
                "❌ Failed to send message. Please try again later."
            )

async def informusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is only for administrators.")
        return
    
    user_states[ADMIN_ID] = {"state": "waiting_broadcast"}
    await update.message.reply_text(
        "Write what you want to inform all the users. I will forward."
    )

async def senduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is only for administrators.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Sorry, incorrect format of command. Use /senduser @username message"
        )
        return
    
    target_username = context.args[0].lstrip("@")
    message = " ".join(context.args[1:])
    
    target_user_id = None
    for uid, data in user_messages.items():
        if data["username"].lstrip("@").lower() == target_username.lower():
            target_user_id = uid
            break
    
    if not target_user_id:
        await update.message.reply_text(
            "Sorry, invalid user name"
        )
        return
    
    success = await send_to_user(target_user_id, message, context)
    if success:
        await update.message.reply_text(
            f"The message sent to @{target_username}."
        )
    else:
        await update.message.reply_text(
            "❌ Failed to send message. The user might have blocked the bot."
        )

ptb.add_handler(CommandHandler("start", start))
ptb.add_handler(CommandHandler("informusers", informusers_command))
ptb.add_handler(CommandHandler("senduser", senduser_command))
ptb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting bot...")
    
    await ptb.initialize()
    
    webhook_info = await ptb.bot.get_webhook_info()
    if webhook_info.url != WEBHOOK_URL:
        await ptb.bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook set to: {WEBHOOK_URL}")
    else:
        logger.info(f"Webhook already set to: {WEBHOOK_URL}")
    
    await ptb.bot.send_message(ADMIN_ID, "Admin, I will forward you the user's message to you.")
    
    commands = [
        ("start", "Start the bot"),
        ("informusers", "Inform all users (admin)"),
        ("senduser", "Send to specific user (admin)")
    ]
    await ptb.bot.set_my_commands(commands)
    logger.info("Bot commands set")
    
    yield
    
    logger.info("Shutting down bot...")
    await ptb.bot.delete_webhook()
    await ptb.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def webhook_post(request: Request):
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
    return {"status": "ok", "message": "Webhook is active"}

@app.get("/")
async def root():
    return {
        "status": "running",
        "bot": "Blind Tech Visionary Feedback Bot",
        "users": len(user_messages)
    }

@app.get("/health")
async def health():
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