from fastapi import FastAPI, Request, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Dict

TOKEN = "8439254355:AAF61_xtEU8EXfVjw8MfdMxghuCk5jyZhhw"
ADMIN_ID = 7026190306
WEBHOOK_URL = "https://blindtechvisionaryfeedbackbot.vercel.app/webhook"

user_messages: Dict[int, dict] = {}
user_states: Dict[int, dict] = {}

ptb = Application.builder().updater(None).token(TOKEN).read_timeout(7).get_updates_read_timeout(42).build()

def get_user_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Reply this message", callback_data="user_reply")],
        [InlineKeyboardButton("New message", callback_data="user_new_message")]
    ])

def get_admin_keyboard(user_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Reply this message", callback_data=f"admin_reply_{user_id}")],
        [InlineKeyboardButton("Send message to all", callback_data="admin_send_all")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    welcome_text = "Welcome to blind tech visionary feedback bot. This telegram bot is designed to collect feedback from you and send to the admin of blind tech visionary community. Start giving your feedback. You can reply the admin later."
    
    if user_id == ADMIN_ID:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Send message to all", callback_data="admin_send_all")]])
        await update.message.reply_text(welcome_text, reply_markup=keyboard)
    else:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Send new message", callback_data="user_new_message")]])
        await update.message.reply_text(welcome_text, reply_markup=keyboard)

async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name or str(user_id)
    
    user_messages[user_id] = {"username": username, "user_id": user_id}
    
    caption_text = f"@{username}:"
    if update.message.caption:
        caption_text += f"\n{update.message.caption}"
    
    admin_kb = get_admin_keyboard(user_id)
    
    try:
        if update.message.text:
            await context.bot.send_message(ADMIN_ID, f"@{username}:\n{update.message.text}", reply_markup=admin_kb)
        elif update.message.photo:
            await context.bot.send_photo(ADMIN_ID, update.message.photo[-1].file_id, caption=caption_text, reply_markup=admin_kb)
        elif update.message.video:
            await context.bot.send_video(ADMIN_ID, update.message.video.file_id, caption=caption_text, reply_markup=admin_kb)
        elif update.message.document:
            await context.bot.send_document(ADMIN_ID, update.message.document.file_id, caption=caption_text, reply_markup=admin_kb)
        elif update.message.audio:
            await context.bot.send_audio(ADMIN_ID, update.message.audio.file_id, caption=caption_text, reply_markup=admin_kb)
        elif update.message.voice:
            await context.bot.send_voice(ADMIN_ID, update.message.voice.file_id, caption=caption_text, reply_markup=admin_kb)
        elif update.message.video_note:
            await context.bot.send_video_note(ADMIN_ID, update.message.video_note.file_id, reply_markup=admin_kb)
        elif update.message.sticker:
            await context.bot.send_sticker(ADMIN_ID, update.message.sticker.file_id, reply_markup=admin_kb)
            await context.bot.send_message(ADMIN_ID, f"@{username}: (sticker)", reply_markup=admin_kb)
    except Exception as e:
        pass

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_states.get(user_id, {}).get("state")
    
    if user_id == ADMIN_ID:
        await handle_admin_message(update, context)
        return
    
    if state:
        await handle_user_state(update, context)
    else:
        await forward_to_admin(update, context)
        await update.message.reply_text("Your message sent successfully to admin.", reply_markup=get_user_keyboard())

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = user_states.get(ADMIN_ID, {}).get("state")
    
    if state == "waiting_broadcast":
        message_text = update.message.text or update.message.caption
        for uid in user_messages.keys():
            try:
                if update.message.text:
                    await context.bot.send_message(uid, message_text, reply_markup=get_user_keyboard())
                elif update.message.photo:
                    await context.bot.send_photo(uid, update.message.photo[-1].file_id, caption=message_text, reply_markup=get_user_keyboard())
                elif update.message.video:
                    await context.bot.send_video(uid, update.message.video.file_id, caption=message_text, reply_markup=get_user_keyboard())
                elif update.message.document:
                    await context.bot.send_document(uid, update.message.document.file_id, caption=message_text, reply_markup=get_user_keyboard())
            except Exception as e:
                pass
        await update.message.reply_text("Message sent to all users successfully.")
        user_states[ADMIN_ID] = {}
        
    elif state == "waiting_admin_reply":
        target_user_id = user_states[ADMIN_ID].get("target_user_id")
        if target_user_id:
            try:
                if update.message.text:
                    await context.bot.send_message(target_user_id, update.message.text, reply_markup=get_user_keyboard())
                elif update.message.photo:
                    await context.bot.send_photo(target_user_id, update.message.photo[-1].file_id, caption=update.message.caption, reply_markup=get_user_keyboard())
                elif update.message.video:
                    await context.bot.send_video(target_user_id, update.message.video.file_id, caption=update.message.caption, reply_markup=get_user_keyboard())
                elif update.message.document:
                    await context.bot.send_document(target_user_id, update.message.document.file_id, caption=update.message.caption, reply_markup=get_user_keyboard())
                await update.message.reply_text("You replied successfully.")
            except Exception as e:
                await update.message.reply_text("Failed to send reply.")
        user_states[ADMIN_ID] = {}

async def handle_user_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = user_states.get(user_id, {}).get("state")
    
    if state in ["waiting_new_message", "waiting_reply"]:
        await forward_to_admin(update, context)
        if state == "waiting_new_message":
            await update.message.reply_text("Your message sent successfully to admin.", reply_markup=get_user_keyboard())
        else:
            await update.message.reply_text("Your reply sent successfully.", reply_markup=get_user_keyboard())
        user_states[user_id] = {}

async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id == ADMIN_ID:
        if not context.args or len(context.args) < 2:
            await update.message.reply_text("Usage: /reply @username your reply message")
            return
        
        target_username = context.args[0].replace("@", "")
        reply_text = " ".join(context.args[1:])
        
        target_user_id = None
        for uid, data in user_messages.items():
            if data["username"].replace("@", "") == target_username:
                target_user_id = uid
                break
        
        if target_user_id:
            try:
                await context.bot.send_message(target_user_id, reply_text, reply_markup=get_user_keyboard())
                await update.message.reply_text("You replied successfully.")
            except Exception as e:
                await update.message.reply_text("Failed to send reply.")
        else:
            await update.message.reply_text("User not found.")
    else:
        user_states[user_id] = {"state": "waiting_reply"}
        await update.message.reply_text("Write your reply for admin:")

async def sendnewmessage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = {"state": "waiting_new_message"}
    await update.message.reply_text("Write your new message for admin:")

async def sendmessagetoall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    user_states[ADMIN_ID] = {"state": "waiting_broadcast"}
    await update.message.reply_text("Write your message to send to all users:")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "user_new_message":
        user_states[user_id] = {"state": "waiting_new_message"}
        await query.message.reply_text("Write your new message for admin:")
    
    elif data == "user_reply":
        user_states[user_id] = {"state": "waiting_reply"}
        await query.message.reply_text("Write your reply for admin:")
    
    elif data.startswith("admin_reply_"):
        target_user_id = int(data.split("_")[2])
        user_states[ADMIN_ID] = {"state": "waiting_admin_reply", "target_user_id": target_user_id}
        await query.message.reply_text("Write your reply for the user:")
    
    elif data == "admin_send_all":
        user_states[ADMIN_ID] = {"state": "waiting_broadcast"}
        await query.message.reply_text("Write your message to send to all users:")

ptb.add_handler(CommandHandler("start", start))
ptb.add_handler(CommandHandler("reply", reply_command))
ptb.add_handler(CommandHandler("sendnewmessage", sendnewmessage_command))
ptb.add_handler(CommandHandler("sendmessagetoall", sendmessagetoall_command))
ptb.add_handler(CallbackQueryHandler(button_callback))
ptb.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

@asynccontextmanager
async def lifespan(_: FastAPI):
    await ptb.bot.set_webhook(url=WEBHOOK_URL)
    async with ptb:
        await ptb.start()
        commands = [
            ("start", "Start the bot"),
            ("reply", "Reply to a message"),
            ("sendnewmessage", "Send new message to admin"),
            ("sendmessagetoall", "Send message to all users (admin only)")
        ]
        await ptb.bot.set_my_commands(commands)
        yield
        await ptb.stop()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, ptb.bot)
        await ptb.process_update(update)
        return Response(status_code=HTTPStatus.OK)
    except Exception as e:
        return Response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

@app.get("/")
async def root():
    return {"status": "running"}

@app.get("/set_webhook")
async def set_webhook_route():
    await ptb.bot.set_webhook(url=WEBHOOK_URL)
    info = await ptb.bot.get_webhook_info()
    return {"webhook_set": WEBHOOK_URL, "webhook_info": str(info)}