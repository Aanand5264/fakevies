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
from threading import Thread

# === Bot Configuration ===
TOKEN = "7793831886:AAFTL9FWQDjfT97fSV-51jBCA9Tysz8fsKg"
DATABASE_NAME = "bot_data.db"

# === Flask Web Server to Keep Alive ===
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and posting news every 30 minutes!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# === Database Functions ===
def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        api_url TEXT,
        api_key TEXT,
        service_id TEXT,
        quantity INTEGER
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        channel_identifier TEXT UNIQUE,
        is_id BOOLEAN DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT api_url, api_key, service_id, quantity FROM users WHERE user_id = ?', (user_id,))
    api_data = cursor.fetchone()
    
    cursor.execute('SELECT channel_identifier, is_id FROM channels WHERE user_id = ?', (user_id,))
    channels = cursor.fetchall()
    
    conn.close()
    
    api_dict = {}
    if api_data:
        api_dict = {
            "url": api_data[0],
            "key": api_data[1],
            "service": api_data[2],
            "quantity": api_data[3]
        }
    
    return {
        "channels": channels,
        "api": api_dict
    }

def save_user_data(user_id, data):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    api = data.get("api", {})
    cursor.execute('''
    INSERT OR REPLACE INTO users (user_id, api_url, api_key, service_id, quantity)
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
        identifier, is_id = channel
        cursor.execute('''
        INSERT INTO channels (user_id, channel_identifier, is_id)
        VALUES (?, ?, ?)
        ''', (user_id, identifier, is_id))
    
    conn.commit()
    conn.close()

# === Telegram Bot Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = get_user_data(user_id)
    
    keyboard = [
        [InlineKeyboardButton("#1 🔧 SMM Settings", callback_data="smm_settings")],
        [InlineKeyboardButton("#2 ➕➖ Channel Add/Remove", callback_data="channel_settings")],
        [InlineKeyboardButton("#3 💰 Check Balance", callback_data="check_balance")],
        [InlineKeyboardButton("#4 Order Views 📈", callback_data="order_views")],
    ]
    await update.message.reply_text("Welcome to AEK Bot!", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = get_user_data(user_id)

    match query.data:
        case "smm_settings":
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
                [InlineKeyboardButton("🛠 Edit SMM", callback_data="edit_smm")],
            ]
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

        case "add_smm":
            context.user_data["add_api_step"] = 1
            await query.edit_message_text("Please enter SMM API URL:")

        case "edit_smm":
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
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

        case "edit_api_url":
            context.user_data["editing"] = "url"
            await query.edit_message_text("Enter new API URL:")

        case "edit_api_key":
            context.user_data["editing"] = "key"
            await query.edit_message_text("Enter new API Key:")

        case "edit_service_id":
            context.user_data["editing"] = "service"
            await query.edit_message_text("Enter new Service ID:")

        case "edit_quantity":
            context.user_data["editing"] = "quantity"
            await query.edit_message_text("Enter new default quantity:")

        case "remove_api":
            data["api"] = {}
            save_user_data(user_id, data)
            await query.edit_message_text("✅ SMM API configuration has been removed.")

        case "channel_settings":
            keyboard = [
                [InlineKeyboardButton("➕ Add Channel", callback_data="add_channel")],
                [InlineKeyboardButton("➖ Remove Channel", callback_data="remove_channel")],
            ]
            await query.edit_message_text("Channel Settings:", reply_markup=InlineKeyboardMarkup(keyboard))

        case "add_channel":
            context.user_data["add_channel_step"] = 1
            await query.edit_message_text(
                "Please enter your channel identifier:\n"
                "For public channels: @username\n"
                "For private channels: id:12345\n\n"
                "Note: The bot must be added as an admin to monitor posts."
            )

        case "remove_channel":
            channels = data.get("channels", [])
            if not channels:
                await query.edit_message_text("❌ No channels to remove.")
                return
            keyboard = [[InlineKeyboardButton(chan[0], callback_data=f"remove_{chan[0]}")] for chan in channels]
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="channel_settings")])
            await query.edit_message_text("Choose a channel to remove:", reply_markup=InlineKeyboardMarkup(keyboard))

        case "check_balance":
            api = data.get("api")
            if not api:
                await query.edit_message_text("❌ API not found in your SMM settings!")
                return
            try:
                response = requests.post(api['url'], data={"key": api['key'], "action": "balance"})
                if response.status_code == 200:
                    res = response.json()
                    balance = res.get("balance", "Unknown")
                    currency = res.get("currency", "")
                    await query.edit_message_text(f"💰 Your balance: {balance} {currency}")
                else:
                    await query.edit_message_text("❌ Failed to fetch balance.")
            except Exception as e:
                await query.edit_message_text(f"❌ Error checking balance: {str(e)}")

        case "order_views":
            context.user_data["order_step"] = 1
            await query.edit_message_text("Send the post link:")

        case _:
            if query.data.startswith("remove_"):
                channel = query.data.split("_")[1]
                new_channels = [chan for chan in data.get("channels", []) if chan[0] != channel]
                data["channels"] = new_channels
                save_user_data(user_id, data)
                await query.edit_message_text(f"✅ Channel {channel} removed successfully.")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.channel_post:
        return

    if not update.effective_user:
        return

    user_id = str(update.effective_user.id)
    text = update.message.text
    data = get_user_data(user_id)

    if "add_channel_step" in context.user_data:
        step = context.user_data["add_channel_step"]
        if step == 1:
            channel = text.strip()
            
            # Validate channel identifier format
            if channel.startswith("@"):
                is_id = False
            elif channel.startswith("id:"):
                try:
                    int(channel[3:])
                    is_id = True
                except ValueError:
                    await update.message.reply_text("❌ Invalid channel ID format. After 'id:' should be numbers only.")
                    return
            else:
                await update.message.reply_text(
                    "❌ Invalid format. Please specify channel as:\n"
                    "- @username for public channels\n"
                    "- id:12345 for private channels"
                )
                return

            # Check if already exists
            current_channels = [chan[0] for chan in data.get("channels", [])]
            if channel not in current_channels:
                data.setdefault("channels", []).append((channel, is_id))
                save_user_data(user_id, data)
            
            context.user_data.pop("add_channel_step")
            await update.message.reply_text(
                f"✅ Channel {channel} added successfully!\n\n"
                "Note: The bot must be added as an admin to monitor posts."
            )

    elif "add_api_step" in context.user_data:
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
                quantity = int(text)
                data["api"] = {
                    "url": context.user_data["api_url"],
                    "key": context.user_data["api_key"],
                    "service": context.user_data["service_id"],
                    "quantity": quantity
                }
                save_user_data(user_id, data)
                context.user_data.clear()
                await update.message.reply_text("✅ SMM API configured successfully!")
            except ValueError:
                await update.message.reply_text("❌ Quantity must be a number!")

    elif "editing" in context.user_data:
        editing = context.user_data["editing"]
        text = update.message.text
        
        if editing == "quantity":
            try:
                value = int(text)
            except ValueError:
                await update.message.reply_text("❌ Quantity must be a number!")
                return
        else:
            value = text.strip()
        
        data["api"][editing] = value
        save_user_data(user_id, data)
        
        await update.message.reply_text(f"✅ {editing.replace('_', ' ').title()} updated successfully!")
        context.user_data.pop("editing")

    elif "order_step" in context.user_data:
        step = context.user_data["order_step"]
        if step == 1:
            context.user_data["order_link"] = text
            context.user_data["order_step"] = 2
            await update.message.reply_text("Enter how many views you want:")
        elif step == 2:
            try:
                qty = int(text)
                api = data.get("api")
                if not api:
                    await update.message.reply_text("❌ API not found in your SMM settings! Please add it first.")
                    return
                
                response = requests.post(api['url'], data={
                    "key": api['key'],
                    "action": "add",
                    "service": api['service'],
                    "link": context.user_data['order_link'],
                    "quantity": qty
                })
                
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
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {str(e)}")
            finally:
                context.user_data.pop("order_step", None)
                context.user_data.pop("order_link", None)

async def handle_new_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.channel_post:
        return

    chat = update.channel_post.chat
    message_id = update.channel_post.message_id

    # Get all possible identifiers
    channel_id = chat.id
    channel_username = getattr(chat, 'username', '').lower()
    
    print(f"New post detected from channel ID: {channel_id}, username: @{channel_username}")

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Search by both username and ID
    cursor.execute('''
    SELECT DISTINCT u.user_id, u.api_url, u.api_key, u.service_id, u.quantity
    FROM users u
    JOIN channels c ON u.user_id = c.user_id
    WHERE (c.is_id = 0 AND LOWER(c.channel_identifier) = LOWER(?))
       OR (c.is_id = 1 AND c.channel_identifier = ?)
    AND u.api_url IS NOT NULL
    AND u.api_key IS NOT NULL
    AND u.service_id IS NOT NULL
    ''', (f"@{channel_username}", f"id:{channel_id}"))
    
    users = cursor.fetchall()
    conn.close()

    if not users:
        print(f"No subscribers found for this channel (tried @{channel_username} and id:{channel_id})")
        return

    for user in users:
        user_id, api_url, api_key, service_id, quantity = user
        if not quantity:
            quantity = 1000
            
        post_link = f"https://t.me/{channel_username}/{message_id}" if channel_username else f"Channel ID: {channel_id}"
        
        try:
            response = requests.post(api_url, data={
                "key": api_key,
                "action": "add",
                "service": service_id,
                "link": post_link,
                "quantity": quantity
            })

            if response.status_code == 200:
                res = response.json()
                if res.get("order"):
                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=f"🚀 Auto-Order Placed!\n\n"
                                 f"📢 Channel: {'@'+channel_username if channel_username else 'ID:'+str(channel_id)}\n"
                                 f"🔗 Post: {post_link}\n"
                                 f"📈 Views: {quantity}\n"
                                 f"🆔 Order ID: {res['order']}\n"
                                 f"💰 Estimated Cost: {res.get('price', 'Unknown')}"
                        )
                    except Exception as e:
                        print(f"Couldn't notify user {user_id}: {str(e)}")
        except Exception as e:
            print(f"Error processing {post_link} for user {user_id}: {str(e)}")

async def channel_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to check if bot can see channel info"""
    if update.effective_chat.type == "channel":
        chat = update.effective_chat
        bot_member = await chat.get_member(context.bot.id)
        
        message = (
            f"📢 Channel Info:\n\n"
            f"ID: {chat.id}\n"
            f"Username: @{getattr(chat, 'username', 'N/A')}\n"
            f"Title: {getattr(chat, 'title', 'N/A')}\n"
            f"Type: {chat.type}\n\n"
            f"Bot Status: {bot_member.status}\n"
            f"Admin Permissions: {getattr(bot_member, 'can_post_messages', 'N/A')}"
        )
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("⚠️ This command only works in channels")

if __name__ == '__main__':
    # Start the keep-alive server
    keep_alive()
    
    # Initialize the database
    init_db()
    
    # Create and run the Telegram bot
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("channelinfo", channel_info))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.ChatType.CHANNEL,
        message_handler
    ))
    
    app.add_handler(MessageHandler(
        filters.ChatType.CHANNEL,
        handle_new_channel_post
    ))
    
    app.run_polling()
