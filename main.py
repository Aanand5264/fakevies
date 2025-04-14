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

# Configuration
TOKEN = "7793831886:AAFTL9FWQDjfT97fSV-51jBCA9Tysz8fsKg"
DATABASE_NAME = "bot_data.db"
PORT = 10000  # Required for Render

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database functions
def init_db():
    """Initialize the database with required tables"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            api_url TEXT,
            api_key TEXT,
            service_id TEXT,
            quantity INTEGER DEFAULT 1000
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            channel_username TEXT UNIQUE,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
        ''')
        
        conn.commit()

def get_user_data(user_id):
    """Get all data for a specific user"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        
        # Get API data
        cursor.execute('''
        SELECT api_url, api_key, service_id, quantity 
        FROM users WHERE user_id = ?
        ''', (user_id,))
        api_data = cursor.fetchone()
        
        # Get channels
        cursor.execute('''
        SELECT channel_username FROM channels WHERE user_id = ?
        ''', (user_id,))
        channels = [row[0] for row in cursor.fetchall()]
        
        api_dict = {}
        if api_data:
            api_dict = {
                "url": api_data[0],
                "key": api_data[1],
                "service": api_data[2],
                "quantity": api_data[3] or 1000
            }
        
        return {
            "channels": channels,
            "api": api_dict
        }

def save_user_data(user_id, data):
    """Save user data to database"""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        
        api = data.get("api", {})
        
        # Upsert user data
        cursor.execute('''
        INSERT INTO users (user_id, api_url, api_key, service_id, quantity)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            api_url = excluded.api_url,
            api_key = excluded.api_key,
            service_id = excluded.service_id,
            quantity = excluded.quantity
        ''', (
            user_id,
            api.get("url"),
            api.get("key"),
            api.get("service"),
            api.get("quantity", 1000)
        ))
        
        # Update channels
        cursor.execute('DELETE FROM channels WHERE user_id = ?', (user_id,))
        for channel in data.get("channels", []):
            try:
                cursor.execute('''
                INSERT INTO channels (user_id, channel_username)
                VALUES (?, ?)
                ''', (user_id, channel))
            except sqlite3.IntegrityError:
                logger.warning(f"Channel {channel} already exists for another user")
        
        conn.commit()

# Initialize database on startup
init_db()

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message with main menu"""
    user_id = str(update.effective_user.id)
    
    keyboard = [
        [InlineKeyboardButton("#1 🔧 SMM Settings", callback_data="smm_settings")],
        [InlineKeyboardButton("#2 ➕➖ Channel Management", callback_data="channel_settings")],
        [InlineKeyboardButton("#3 💰 Check Balance", callback_data="check_balance")],
        [InlineKeyboardButton("#4 📈 Order Views", callback_data="order_views")],
    ]
    
    await update.message.reply_text(
        "🚀 Welcome to AEK SMM Bot!\n\n"
        "Please select an option from the menu below:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all button callbacks"""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = get_user_data(user_id)

    try:
        if query.data == "smm_settings":
            await handle_smm_settings(query, data)
        elif query.data == "add_smm":
            await handle_add_smm(query)
        elif query.data == "edit_smm":
            await handle_edit_smm(query, data)
        elif query.data.startswith("edit_"):
            await handle_edit_field(query, query.data[5:])
        elif query.data == "remove_api":
            await handle_remove_api(query, user_id, data)
        elif query.data == "channel_settings":
            await handle_channel_settings(query)
        elif query.data == "add_channel":
            await handle_add_channel(query)
        elif query.data == "remove_channel":
            await handle_remove_channel(query, data)
        elif query.data.startswith("remove_"):
            await handle_remove_specific_channel(query, user_id, data)
        elif query.data == "check_balance":
            await handle_check_balance(query, data)
        elif query.data == "order_views":
            await handle_order_views(query)
        else:
            await query.edit_message_text("❌ Unknown command. Please try again.")
    except Exception as e:
        logger.error(f"Error in button handler: {str(e)}")
        await query.edit_message_text("❌ An error occurred. Please try again.")

async def handle_smm_settings(query, data):
    """Handle SMM settings menu"""
    api = data.get("api", {})
    if api:
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
        [InlineKeyboardButton("🛠 Edit SMM API", callback_data="edit_smm")],
    ]
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_add_smm(query):
    """Initiate SMM API setup process"""
    context.user_data["add_api_step"] = 1
    await query.edit_message_text(
        "Please enter your SMM API URL:\n\n"
        "Example: https://example.com/api/v2"
    )

async def handle_edit_smm(query, data):
    """Handle SMM API editing menu"""
    if not data.get("api"):
        await query.edit_message_text("❌ No SMM API found. Please add it first.")
        return
    
    message = (
        "📝 Edit SMM API Settings:\n\n"
        f"1. URL: {data['api'].get('url', 'Not set')}\n"
        f"2. Key: {'*' * 8 if data['api'].get('key') else 'Not set'}\n"
        f"3. Service ID: {data['api'].get('service', 'Not set')}\n"
        f"4. Quantity: {data['api'].get('quantity', 'Not set')}\n\n"
        "Choose what to edit:"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔗 Edit API URL", callback_data="edit_url")],
        [InlineKeyboardButton("🔑 Edit API Key", callback_data="edit_key")],
        [InlineKeyboardButton("🆔 Edit Service ID", callback_data="edit_service")],
        [InlineKeyboardButton("📊 Edit Quantity", callback_data="edit_quantity")],
        [InlineKeyboardButton("❌ Remove API", callback_data="remove_api")],
        [InlineKeyboardButton("🔙 Back", callback_data="smm_settings")],
    ]
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_edit_field(query, field):
    """Handle editing of specific API fields"""
    context.user_data["editing"] = field
    await query.edit_message_text(f"Enter new {field.replace('_', ' ')}:")

async def handle_remove_api(query, user_id, data):
    """Remove SMM API configuration"""
    data["api"] = {}
    save_user_data(user_id, data)
    await query.edit_message_text("✅ SMM API configuration has been removed.")

async def handle_channel_settings(query):
    """Handle channel management menu"""
    keyboard = [
        [InlineKeyboardButton("➕ Add Channel", callback_data="add_channel")],
        [InlineKeyboardButton("➖ Remove Channel", callback_data="remove_channel")],
        [InlineKeyboardButton("🔙 Back", callback_data="start")]
    ]
    await query.edit_message_text(
        "📢 Channel Management\n\n"
        "Add or remove channels for auto-ordering views",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_add_channel(query):
    """Initiate channel addition process"""
    context.user_data["add_channel_step"] = 1
    await query.edit_message_text(
        "Please enter your channel username (e.g., @your_channel):\n\n"
        "⚠️ Important: The bot must be an admin in your channel to monitor posts."
    )

async def handle_remove_channel(query, data):
    """Show channel removal options"""
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
        "Select a channel to remove:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_remove_specific_channel(query, user_id, data):
    """Remove a specific channel"""
    channel = query.data.split("_")[1]
    if channel in data.get("channels", []):
        data["channels"].remove(channel)
        save_user_data(user_id, data)
        await query.edit_message_text(f"✅ Channel {channel} removed successfully.")
    else:
        await query.edit_message_text(f"❌ Channel {channel} not found.")

async def handle_check_balance(query, data):
    """Check SMM panel balance"""
    api = data.get("api")
    if not api:
        await query.edit_message_text("❌ API not configured. Please set up your SMM API first.")
        return
    
    try:
        response = requests.post(
            api['url'],
            data={"key": api['key'], "action": "balance"},
            timeout=10
        )
        
        if response.status_code == 200:
            res = response.json()
            balance = res.get("balance", "Unknown")
            currency = res.get("currency", "")
            await query.edit_message_text(f"💰 Your balance: {balance} {currency}")
        else:
            await query.edit_message_text("❌ Failed to fetch balance. Please check your API settings.")
    except Exception as e:
        logger.error(f"Balance check error: {str(e)}")
        await query.edit_message_text(f"❌ Error checking balance: {str(e)}")

async def handle_order_views(query):
    """Initiate view ordering process"""
    context.user_data["order_step"] = 1
    await query.edit_message_text(
        "Please send the post link you want to boost:\n\n"
        "Example: https://t.me/your_channel/123"
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    if update.channel_post or not update.effective_user:
        return

    user_id = str(update.effective_user.id)
    text = update.message.text
    data = get_user_data(user_id)

    try:
        if "add_channel_step" in context.user_data:
            await handle_add_channel_message(update, context, data)
        elif "add_api_step" in context.user_data:
            await handle_add_api_message(update, context, data)
        elif "editing" in context.user_data:
            await handle_edit_message(update, context, data)
        elif "order_step" in context.user_data:
            await handle_order_message(update, context, data)
        else:
            await update.message.reply_text("Please use the menu buttons to interact with the bot.")
    except Exception as e:
        logger.error(f"Message handler error: {str(e)}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

async def handle_add_channel_message(update, context, data):
    """Handle channel addition process"""
    channel = update.message.text.strip()
    if not channel.startswith("@"):
        await update.message.reply_text("❌ Invalid format. Channel must start with @ (e.g., @your_channel)")
        return

    if channel in data.get("channels", []):
        await update.message.reply_text(f"ℹ️ Channel {channel} is already in your list.")
    else:
        data["channels"].append(channel)
        save_user_data(update.effective_user.id, data)
        await update.message.reply_text(
            f"✅ Channel {channel} added successfully!\n\n"
            "Remember to make the bot an admin in your channel."
        )
    context.user_data.pop("add_channel_step", None)

async def handle_add_api_message(update, context, data):
    """Handle SMM API setup process"""
    step = context.user_data["add_api_step"]
    text = update.message.text.strip()
    
    if step == 1:  # API URL
        if not text.startswith(('http://', 'https://')):
            await update.message.reply_text("❌ Invalid URL. Please enter a valid HTTP/HTTPS URL.")
            return
        context.user_data["api_url"] = text
        context.user_data["add_api_step"] = 2
        await update.message.reply_text("Please enter your API Key:")
    
    elif step == 2:  # API Key
        if len(text) < 10:
            await update.message.reply_text("❌ API Key seems too short. Please check and try again.")
            return
        context.user_data["api_key"] = text
        context.user_data["add_api_step"] = 3
        await update.message.reply_text("Please enter the Service ID:")
    
    elif step == 3:  # Service ID
        if not text.isdigit():
            await update.message.reply_text("❌ Service ID should be a number. Please check your SMM panel.")
            return
        context.user_data["service_id"] = text
        context.user_data["add_api_step"] = 4
        await update.message.reply_text("Please enter default quantity (number of views per order):")
    
    elif step == 4:  # Quantity
        try:
            quantity = int(text)
            if quantity <= 0:
                raise ValueError
                
            data["api"] = {
                "url": context.user_data["api_url"],
                "key": context.user_data["api_key"],
                "service": context.user_data["service_id"],
                "quantity": quantity
            }
            save_user_data(update.effective_user.id, data)
            
            await update.message.reply_text(
                "✅ SMM API configured successfully!\n\n"
                "You can now check your balance or order views."
            )
            context.user_data.clear()
        except ValueError:
            await update.message.reply_text("❌ Quantity must be a positive number. Please try again.")

async def handle_edit_message(update, context, data):
    """Handle editing of API settings"""
    field = context.user_data["editing"]
    text = update.message.text.strip()
    
    if field == "quantity":
        try:
            value = int(text)
            if value <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Quantity must be a positive number!")
            return
    else:
        value = text
    
    data["api"][field] = value
    save_user_data(update.effective_user.id, data)
    
    await update.message.reply_text(f"✅ {field.replace('_', ' ').title()} updated successfully!")
    context.user_data.pop("editing")

async def handle_order_message(update, context, data):
    """Handle view ordering process"""
    step = context.user_data["order_step"]
    text = update.message.text.strip()
    
    if step == 1:  # Post link
        if not text.startswith(('https://t.me/', 'http://t.me/')):
            await update.message.reply_text("❌ Invalid Telegram post link. It should start with https://t.me/")
            return
        context.user_data["order_link"] = text
        context.user_data["order_step"] = 2
        await update.message.reply_text("Enter how many views you want:")
    
    elif step == 2:  # Quantity
        try:
            qty = int(text)
            if qty <= 0:
                raise ValueError
                
            api = data.get("api")
            if not api:
                await update.message.reply_text("❌ API not configured. Please set up your SMM API first.")
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
                timeout=15
            )
            
            if response.status_code == 200:
                res = response.json()
                if res.get("order"):
                    await update.message.reply_text(
                        f"✅ Order Placed Successfully!\n\n"
                        f"🔗 Post: {context.user_data['order_link']}\n"
                        f"📈 Views: {qty}\n"
                        f"🆔 Order ID: {res['order']}\n"
                        f"💰 Estimated Cost: {res.get('price', 'Unknown')}"
                    )
                else:
                    await update.message.reply_text(f"❌ Failed to place order. Response: {res}")
            else:
                await update.message.reply_text(f"❌ API Error: {response.status_code}")
        except ValueError:
            await update.message.reply_text("❌ Quantity must be a positive number!")
        except requests.Timeout:
            await update.message.reply_text("❌ Request timed out. Please try again later.")
        except Exception as e:
            logger.error(f"Order error: {str(e)}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
        finally:
            context.user_data.pop("order_step", None)
            context.user_data.pop("order_link", None)

async def handle_new_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Automatically process new channel posts"""
    if not update.channel_post:
        return

    chat = update.channel_post.chat
    message_id = update.channel_post.message_id

    if not chat.username:
        return  # Skip private channels

    channel_mention = f"@{chat.username}"
    post_link = f"https://t.me/{chat.username}/{message_id}"

    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT DISTINCT u.user_id, u.api_url, u.api_key, u.service_id, u.quantity
        FROM users u
        JOIN channels c ON u.user_id = c.user_id
        WHERE c.channel_username = ?
        AND u.api_url IS NOT NULL
        AND u.api_key IS NOT NULL
        AND u.service_id IS NOT NULL
        ''', (channel_mention,))
        
        users = cursor.fetchall()

    for user in users:
        user_id, api_url, api_key, service_id, quantity = user
        if not quantity:
            quantity = 1000
            
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
                timeout=15
            )

            if response.status_code == 200:
                res = response.json()
                if res.get("order"):
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=(
                                f"🚀 Auto-Order Placed!\n\n"
                                f"📢 Channel: {channel_mention}\n"
                                f"🔗 Post: {post_link}\n"
                                f"📈 Views: {quantity}\n"
                                f"🆔 Order ID: {res['order']}\n"
                                f"💰 Estimated Cost: {res.get('price', 'Unknown')}"
                            )
                        )
                    except Exception as e:
                        logger.error(f"Notification error for user {user_id}: {str(e)}")
        except Exception as e:
            logger.error(f"Auto-order error for {post_link}: {str(e)}")

def main():
    """Start the bot"""
    application = ApplicationBuilder().token(TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
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

    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()
