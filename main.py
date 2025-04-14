import sqlite3
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
from threading import Thread

# ======================
# CONFIGURATION
# ======================
TOKEN = "7793831886:AAFTL9FWQDjfT97fSV-51jBCA9Tysz8fsKg"
DATABASE_NAME = "bot_data.db"
PORT = 8080

# ======================
# FLASK KEEP-ALIVE SERVER
# ======================
app = Flask(__name__)

@app.route('/')
def home():
    return "Telegram Bot is running and active!"

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

def keep_alive():
    server = Thread(target=run_flask)
    server.start()

# ======================
# DATABASE FUNCTIONS
# ======================
def init_db():
    """Initialize the SQLite database with required tables"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        
        # Users table for API configurations
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            api_url TEXT,
            api_key TEXT,
            service_id TEXT,
            quantity INTEGER
        )
        ''')
        
        # Channels table for user channels
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            channel_username TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        ''')
        conn.commit()

def get_user_data(user_id):
    """Retrieve user data from database"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        
        # Get API configuration
        cursor.execute('''
        SELECT api_url, api_key, service_id, quantity 
        FROM users WHERE user_id = ?
        ''', (user_id,))
        api_data = cursor.fetchone()
        
        # Get subscribed channels
        cursor.execute('''
        SELECT channel_username FROM channels 
        WHERE user_id = ?
        ''', (user_id,))
        channels = [row[0] for row in cursor.fetchall()]
    
    return {
        "api": {
            "url": api_data[0] if api_data else None,
            "key": api_data[1] if api_data else None,
            "service": api_data[2] if api_data else None,
            "quantity": api_data[3] if api_data else None
        },
        "channels": channels
    }

def save_user_data(user_id, data):
    """Save user data to database"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        
        # Save API configuration
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
            api.get("quantity", 1000)
        ))
        
        # Save channels (first remove existing)
        cursor.execute('''
        DELETE FROM channels WHERE user_id = ?
        ''', (user_id,))
        
        for channel in data.get("channels", []):
            cursor.execute('''
            INSERT INTO channels (user_id, channel_username)
            VALUES (?, ?)
            ''', (user_id, channel))
        
        conn.commit()

# ======================
# TELEGRAM BOT HANDLERS
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start command"""
    user_id = str(update.effective_user.id)
    
    # Initialize user data if not exists
    if not get_user_data(user_id)["api"]["url"]:
        save_user_data(user_id, {"api": {}, "channels": []})
    
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

async def handle_smm_settings(update: Update, data: dict):
    """Handle SMM settings menu"""
    query = update.callback_query
    api = data.get("api", {})
    
    if api.get("url"):
        message = (
            "🔧 Current SMM API Settings:\n\n"
            f"🔗 URL: {api.get('url', 'Not set')}\n"
            f"🔑 Key: {'*' * 8 if api.get('key') else 'Not set'}\n"
            f"🆔 Service ID: {api.get('service', 'Not set')}\n"
            f"📊 Default Quantity: {api.get('quantity', 'Not set')}\n\n"
            "Choose an action:"
        )
    else:
        message = "No SMM API configured yet. Please add one:"
    
    keyboard = [
        [InlineKeyboardButton("➕ Add SMM API", callback_data="add_smm")],
        [InlineKeyboardButton("🛠 Edit SMM", callback_data="edit_smm")],
    ]
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_edit_smm(update: Update, data: dict):
    """Handle SMM editing menu"""
    query = update.callback_query
    api = data.get("api", {})
    
    if not api:
        await query.edit_message_text("❌ No SMM API found. Please add it first.")
        return
    
    message = (
        "📝 Edit SMM API Settings:\n\n"
        f"1. URL: {api.get('url', 'Not set')}\n"
        f"2. Key: {'*' * 8 if api.get('key') else 'Not set'}\n"
        f"3. Service ID: {api.get('service', 'Not set')}\n"
        f"4. Quantity: {api.get('quantity', 'Not set')}\n\n"
        "Choose what to edit:"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔗 Edit API URL", callback_data="edit_api_url")],
        [InlineKeyboardButton("🔑 Edit API Key", callback_data="edit_api_key")],
        [InlineKeyboardButton("🆔 Edit Service ID", callback_data="edit_service_id")],
        [InlineKeyboardButton("📊 Edit Quantity", callback_data="edit_quantity")],
        [InlineKeyboardButton("❌ Remove API", callback_data="remove_api")],
        [InlineKeyboardButton("🔙 Back", callback_data="smm_settings")],
    ]
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main callback query handler"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = get_user_data(user_id)

    # Handle different button actions
    if query.data == "smm_settings":
        await handle_smm_settings(update, data)
    elif query.data == "edit_smm":
        await handle_edit_smm(update, data)
    elif query.data == "add_smm":
        context.user_data["add_api_step"] = 1
        await query.edit_message_text("Please enter SMM API URL:")
    elif query.data.startswith("edit_api_"):
        field = query.data.split("_")[-1]
        context.user_data["editing"] = field
        await query.edit_message_text(f"Enter new API {field.replace('_', ' ').title()}:")
    elif query.data == "remove_api":
        save_user_data(user_id, {"api": {}, "channels": data["channels"]})
        await query.edit_message_text("✅ SMM API configuration has been removed.")
    elif query.data == "channel_settings":
        keyboard = [
            [InlineKeyboardButton("➕ Add Channel", callback_data="add_channel")],
            [InlineKeyboardButton("➖ Remove Channel", callback_data="remove_channel")],
        ]
        await query.edit_message_text(
            "Channel Settings:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif query.data == "add_channel":
        context.user_data["add_channel_step"] = 1
        await query.edit_message_text(
            "Please enter your channel username (e.g., @your_channel):\n\n"
            "Note: The bot must be added as an admin to monitor posts."
        )
    elif query.data == "remove_channel":
        channels = data.get("channels", [])
        if not channels:
            await query.edit_message_text("❌ No channels to remove.")
            return
        
        keyboard = [
            [InlineKeyboardButton(channel, callback_data=f"remove_{channel}")] 
            for channel in channels
        ]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="channel_settings")])
        
        await query.edit_message_text(
            "Choose a channel to remove:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif query.data == "check_balance":
        api = data.get("api")
        if not api or not api.get("url"):
            await query.edit_message_text("❌ API not found in your SMM settings!")
            return
        
        try:
            response = requests.post(
                api['url'],
                data={"key": api['key'], "action": "balance"},
                timeout=10
            )
            
            if response.status_code == 200:
                res = response.json()
                await query.edit_message_text(
                    f"💰 Your balance: {res.get('balance', 'Unknown')} "
                    f"{res.get('currency', '')}"
                )
            else:
                await query.edit_message_text("❌ Failed to fetch balance.")
        except Exception as e:
            await query.edit_message_text(f"❌ Error checking balance: {str(e)}")
    
    elif query.data == "order_views":
        context.user_data["order_step"] = 1
        await query.edit_message_text("Send the post link:")
    
    elif query.data.startswith("remove_"):
        channel = query.data.split("_")[1]
        if channel in data.get("channels", []):
            data["channels"].remove(channel)
            save_user_data(user_id, data)
            await query.edit_message_text(f"✅ Channel {channel} removed successfully.")
        else:
            await query.edit_message_text(f"❌ Channel {channel} not found.")

async def handle_api_setup(context, user_id, text, data):
    """Handle multi-step API setup process"""
    step = context.user_data["add_api_step"]
    
    if step == 1:
        context.user_data["api_url"] = text
        context.user_data["add_api_step"] = 2
        return "Please enter API Key:"
    
    elif step == 2:
        context.user_data["api_key"] = text
        context.user_data["add_api_step"] = 3
        return "Please enter Service ID:"
    
    elif step == 3:
        context.user_data["service_id"] = text
        context.user_data["add_api_step"] = 4
        return "Please enter default quantity:"
    
    elif step == 4:
        try:
            quantity = int(text)
            data["api"] = {
                "url": context.user_data["api_url"],
                "key": context.user_data["api_key"],
                "service": context.user_data["service_id"],
                "quantity": quantity
            }
            save_user_data(user_id, data)
            context.user_data.clear()
            return "✅ SMM API configured successfully!"
        except ValueError:
            return "❌ Quantity must be a number!"

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all incoming messages"""
    if update.channel_post or not update.effective_user:
        return

    user_id = str(update.effective_user.id)
    text = update.message.text
    data = get_user_data(user_id)

    if "add_channel_step" in context.user_data:
        if not text.startswith("@"):
            await update.message.reply_text(
                "❌ Invalid format. Please start with @ (e.g., @channel)"
            )
            return
        
        data["channels"].append(text.strip())
        save_user_data(user_id, data)
        context.user_data.pop("add_channel_step")
        await update.message.reply_text(
            f"✅ Channel {text} added!\n\n"
            "Note: The bot must be admin to monitor posts."
        )
    
    elif "add_api_step" in context.user_data:
        response = await handle_api_setup(context, user_id, text, data)
        await update.message.reply_text(response)
    
    elif "editing" in context.user_data:
        field = context.user_data["editing"]
        value = int(text) if field == "quantity" else text.strip()
        
        data["api"][field] = value
        save_user_data(user_id, data)
        context.user_data.pop("editing")
        
        await update.message.reply_text(
            f"✅ {field.replace('_', ' ').title()} updated!"
        )
    
    elif "order_step" in context.user_data:
        step = context.user_data["order_step"]
        
        if step == 1:
            context.user_data["order_link"] = text
            context.user_data["order_step"] = 2
            await update.message.reply_text("Enter view quantity:")
        
        elif step == 2:
            try:
                qty = int(text)
                api = data.get("api")
                
                if not api:
                    await update.message.reply_text("❌ Configure API first!")
                    return
                
                response = requests.post(
                    api['url'],
                    data={
                        "key": api['key'],
                        "action": "add",
                        "service": api['service'],
                        "link": context.user_data['order_link'],
                        "quantity": qty
                    },
                    timeout=10
                )
                
                if response.ok:
                    res = response.json()
                    if res.get("order"):
                        await update.message.reply_text(
                            f"✅ Order Successful!\n\n"
                            f"🔗 Post: {context.user_data['order_link']}\n"
                            f"📈 Views: {qty}\n"
                            f"🆔 Order ID: {res['order']}\n"
                            f"💰 Cost: {res.get('price', 'Unknown')}"
                        )
                    else:
                        await update.message.reply_text(f"❌ Order failed: {res}")
                else:
                    await update.message.reply_text(f"❌ API Error: {response.status_code}")
            
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {str(e)}")
            
            finally:
                context.user_data.pop("order_step", None)
                context.user_data.pop("order_link", None)

async def handle_new_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Automatically process new channel posts"""
    if not update.channel_post or not update.channel_post.chat.username:
        return

    chat = update.channel_post.chat
    post_link = f"https://t.me/{chat.username}/{update.channel_post.message_id}"
    channel_mention = f"@{chat.username}"

    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT u.user_id, u.api_url, u.api_key, u.service_id, u.quantity
        FROM users u
        JOIN channels c ON u.user_id = c.user_id
        WHERE c.channel_username = ?
        AND u.api_url IS NOT NULL
        ''', (channel_mention,))
        
        for user in cursor.fetchall():
            user_id, api_url, api_key, service_id, quantity = user
            quantity = quantity or 1000  # Default quantity
            
            try:
                response = requests.post(
                    api_url,
                    data={
                        "key": api_key,
                        "action": "add",
                        "service": service_id,
                        "link": post_link,
                        "quantity": quantity
                    },
                    timeout=10
                )
                
                if response.ok and response.json().get("order"):
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=(
                            f"🚀 Auto-Order Placed!\n\n"
                            f"📢 Channel: {channel_mention}\n"
                            f"🔗 Post: {post_link}\n"
                            f"📈 Views: {quantity}\n"
                            f"🆔 Order ID: {response.json()['order']}"
                        )
                    )
            
            except Exception as e:
                print(f"Error processing order for {user_id}: {str(e)}")

# ======================
# APPLICATION SETUP
# ======================
def setup_application():
    """Configure and return the Telegram application"""
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Message handlers
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.ChatType.CHANNEL,
        message_handler
    ))
    
    # Channel post handler
    application.add_handler(MessageHandler(
        filters.ChatType.CHANNEL,
        handle_new_channel_post
    ))
    
    return application

if __name__ == '__main__':
    # Start keep-alive server
    keep_alive()
    
    # Initialize database
    init_db()
    
    # Run the bot
    app = setup_application()
    app.run_polling()
