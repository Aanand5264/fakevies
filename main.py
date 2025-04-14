import sqlite3
import logging
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

# ================ CONFIGURATION ================
TOKEN = "7793831886:AAFTL9FWQDjfT97fSV-51jBCA9Tysz8fsKg"
DATABASE_NAME = "bot_data.db"
PORT = 8080

# ================ LOGGING SETUP ================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Silence noisy libraries
for lib in ['httpx', 'telegram', 'werkzeug']:
    logging.getLogger(lib).setLevel(logging.WARNING)

# ================ FLASK SETUP ================
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running", 200

# ================ DATABASE HANDLING ================
class Database:
    @staticmethod
    def init_db():
        with sqlite3.connect(DATABASE_NAME, timeout=10, check_same_thread=False) as conn:
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
            logger.info("Database initialized")

    @staticmethod
    def get_user_data(user_id):
        with sqlite3.connect(DATABASE_NAME, timeout=10, check_same_thread=False) as conn:
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

    @staticmethod
    def save_user_data(user_id, data):
        with sqlite3.connect(DATABASE_NAME, timeout=10, check_same_thread=False) as conn:
            cursor = conn.cursor()
            api = data.get("api", {})
            
            cursor.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, api_url, api_key, service_id, quantity)
            VALUES (?, ?, ?, ?, ?)
            ''', (
                user_id,
                api.get("url"),
                api.get("key"),
                api.get("service"),
                api.get("quantity")
            ))
            
            cursor.execute('DELETE FROM channels WHERE user_id = ?', (user_id,))
            for channel in data.get("channels", []):
                cursor.execute('INSERT INTO channels (user_id, channel_username) VALUES (?, ?)', (user_id, channel))
            
            conn.commit()
            logger.info(f"Data saved for user {user_id}")

# Initialize database
Database.init_db()

# ================ BOT HANDLERS ================
class BotHandlers:
    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = str(update.effective_user.id)
            logger.info(f"Start command from {user_id}")
            
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
        except Exception as e:
            logger.error(f"Start handler error: {str(e)}")

    @staticmethod
    async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            query = update.callback_query
            await query.answer()
            user_id = str(query.from_user.id)
            data = Database.get_user_data(user_id)
            logger.info(f"Button pressed: {query.data} by {user_id}")

            if query.data == "smm_settings":
                api = data.get("api", {})
                message = (
                    "🔧 Current SMM API Settings:\n\n"
                    f"🔗 URL: {api.get('url', 'Not set')}\n"
                    f"🔑 Key: {'*' * 8 if api.get('key') else 'Not set'}\n"
                    f"🆔 Service ID: {api.get('service', 'Not set')}\n"
                    f"📊 Default Quantity: {api.get('quantity', 'Not set')}\n\n"
                    "Choose an action:"
                )
                
                keyboard = [
                    [InlineKeyboardButton("➕ Add SMM API", callback_data="add_smm")],
                    [InlineKeyboardButton("🛠 Edit SMM", callback_data="edit_smm")],
                ]
                await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
            
            elif query.data == "add_smm":
                context.user_data["add_api_step"] = 1
                await query.edit_message_text("Please enter SMM API URL:")
            
            # Add other button handlers here...

        except Exception as e:
            logger.error(f"Button handler error: {str(e)}")

    @staticmethod
    async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if update.channel_post or not update.effective_user:
                return

            user_id = str(update.effective_user.id)
            text = update.message.text
            data = Database.get_user_data(user_id)
            logger.info(f"Message from {user_id}: {text[:50]}...")

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
                        Database.save_user_data(user_id, data)
                        context.user_data.clear()
                        await update.message.reply_text("✅ SMM API configured successfully!")
                    except ValueError:
                        await update.message.reply_text("❌ Quantity must be a number!")

            # Add other message handlers here...

        except Exception as e:
            logger.error(f"Message handler error: {str(e)}")

# ================ SERVER MANAGEMENT ================
def run_flask():
    """Run Flask server with minimal logging"""
    app.run(host='0.0.0.0', port=PORT, debug=False)

async def run_bot():
    """Main bot runner with error handling"""
    try:
        application = ApplicationBuilder().token(TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", BotHandlers.start))
        application.add_handler(CallbackQueryHandler(BotHandlers.button_handler))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.ChatType.CHANNEL,
            BotHandlers.message_handler
        ))
        
        logger.info("Bot starting...")
        await application.run_polling()
    except Exception as e:
        logger.critical(f"Bot crashed: {str(e)}")
        raise

# ================ MAIN ENTRY POINT ================
if __name__ == '__main__':
    # Start Flask in a daemon thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Run bot in main thread
    asyncio.run(run_bot())
