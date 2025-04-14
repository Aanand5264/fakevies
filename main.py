import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import requests
from flask import Flask
import threading
import asyncio

# Initialize Flask app for health checks
app = Flask(__name__)

@app.route('/')
def health_check():
    return "AEK Bot is running", 200

# Configuration
TOKEN = "7793831886:AAFTL9FWQDjfT97fSV-51jBCA9Tysz8fsKg"
DATABASE_NAME = "bot_data.db"

# Database functions
def init_db():
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            api_url TEXT,
            api_key TEXT,
            service_id TEXT,
            quantity INTEGER
        )''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            channel_username TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )''')
        conn.commit()

init_db()

def get_user_data(user_id):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT api_url, api_key, service_id, quantity FROM users WHERE user_id = ?', (user_id,))
        api_data = cursor.fetchone()
        cursor.execute('SELECT channel_username FROM channels WHERE user_id = ?', (user_id,))
        channels = [row[0] for row in cursor.fetchall()]
    
    return {
        "channels": channels,
        "api": {
            "url": api_data[0] if api_data else None,
            "key": api_data[1] if api_data else None,
            "service": api_data[2] if api_data else None,
            "quantity": api_data[3] if api_data else None
        } if api_data else {}
    }

def save_user_data(user_id, data):
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        api = data.get("api", {})
        cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, api_url, api_key, service_id, quantity)
        VALUES (?, ?, ?, ?, ?)
        ''', (user_id, api.get("url"), api.get("key"), api.get("service"), api.get("quantity")))
        
        cursor.execute('DELETE FROM channels WHERE user_id = ?', (user_id,))
        for channel in data.get("channels", []):
            cursor.execute('INSERT INTO channels (user_id, channel_username) VALUES (?, ?)', (user_id, channel))
        conn.commit()

# Bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("#1 🔧 SMM Settings", callback_data="smm_settings")],
        [InlineKeyboardButton("#2 ➕➖ Channel Add/Remove", callback_data="channel_settings")],
        [InlineKeyboardButton("#3 💰 Check Balance", callback_data="check_balance")],
        [InlineKeyboardButton("#4 Order Views 📈", callback_data="order_views")],
    ]
    await update.message.reply_text(
        "Welcome to AEK Bot!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = get_user_data(user_id)

    if query.data == "smm_settings":
        api = data.get("api", {})
        message = ("🔧 Current SMM API Settings:\n\n" +
                  f"🔗 URL: {api.get('url', 'Not set')}\n" +
                  f"🔑 Key: {'*' * 8 if api.get('key') else 'Not set'}\n" +
                  f"🆔 Service ID: {api.get('service', 'Not set')}\n" +
                  f"📊 Default Quantity: {api.get('quantity', 'Not set')}\n\n" +
                  "Choose an action:")
        
        keyboard = [
            [InlineKeyboardButton("➕ Add SMM API", callback_data="add_smm")],
            [InlineKeyboardButton("🛠 Edit SMM", callback_data="edit_smm")],
        ]
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "add_smm":
        context.user_data["add_api_step"] = 1
        await query.edit_message_text("Please enter SMM API URL:")
    
    # [Add all other button handlers from your original code...]

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.channel_post or not update.effective_user:
        return

    user_id = str(update.effective_user.id)
    text = update.message.text
    data = get_user_data(user_id)

    if "add_api_step" in context.user_data:
        step = context.user_data["add_api_step"]
        if step == 1:
            context.user_data["api_url"] = text
            context.user_data["add_api_step"] = 2
            await update.message.reply_text("Please enter API Key:")
        elif step == 2:
            context.user_data["api_key"] = text
            context.user_data["add_api_step"] = 3
            await update.message.reply_text("Please enter Service ID:")
        elif step == 3:
            context.user_data["service_id"] = text
            context.user_data["add_api_step"] = 4
            await update.message.reply_text("Please enter default quantity:")
        elif step == 4:
            try:
                data["api"] = {
                    "url": context.user_data["api_url"],
                    "key": context.user_data["api_key"],
                    "service": context.user_data["service_id"],
                    "quantity": int(text)
                }
                save_user_data(user_id, data)
                context.user_data.clear()
                await update.message.reply_text("✅ SMM API configured successfully!")
            except ValueError:
                await update.message.reply_text("❌ Quantity must be a number!")

    # [Add other message handlers...]

def run_flask():
    app.run(host='0.0.0.0', port=8080)

async def run_bot():
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.ChatType.CHANNEL,
        message_handler
    ))
    
    await application.run_polling()

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    asyncio.run(run_bot())
