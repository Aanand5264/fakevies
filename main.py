import json
import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = "7793831886:AAFwa8jlFh7SiC5Q0PKxxh7IrcXP6v1iKUs"
DATA_FILE = "tmd/data.json"

# Initialize data files
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)

def load_data():
    with open(DATA_FILE) as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = {"channels": [], "api": {}}
        save_data(data)

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
    data = load_data()
    data.setdefault(user_id, {"channels": [], "api": {}})

    match query.data:
        case "smm_settings":
            api = data[user_id].get("api", {})
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

        case "edit_smm":
            api = data[user_id].get("api", {})
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
            data[user_id]["api"] = {}
            save_data(data)
            await query.edit_message_text("✅ SMM API configuration has been removed.")

        case "channel_settings":
            keyboard = [
                [InlineKeyboardButton("➕ Add Channel", callback_data="add_channel")],
                [InlineKeyboardButton("➖ Remove Channel", callback_data="remove_channel")],
            ]
            await query.edit_message_text("Channel Settings:", reply_markup=InlineKeyboardMarkup(keyboard))

        case "add_channel":
            context.user_data["add_channel_step"] = 1
            await query.edit_message_text("Please enter your channel username (e.g., @your_channel):\n\n"
                                        "Note: The bot must be added as an admin to monitor posts.")

        case "remove_channel":
            channels = data[user_id].get("channels", [])
            if not channels:
                await query.edit_message_text("❌ No channels to remove.")
                return
            keyboard = [[InlineKeyboardButton(channel, callback_data=f"remove_{channel}")] for channel in channels]
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="channel_settings")])
            await query.edit_message_text("Choose a channel to remove:", reply_markup=InlineKeyboardMarkup(keyboard))

        case "check_balance":
            api = data[user_id].get("api")
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
                if channel in data[user_id]["channels"]:
                    data[user_id]["channels"].remove(channel)
                    save_data(data)
                    await query.edit_message_text(f"✅ Channel {channel} removed successfully.")
                else:
                    await query.edit_message_text(f"❌ Channel {channel} not found.")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Skip if this is a channel post (handled separately)
    if update.channel_post:
        return

    # Only process user messages
    if not update.effective_user:
        return

    user_id = str(update.effective_user.id)
    text = update.message.text
    data = load_data()
    data.setdefault(user_id, {"channels": [], "api": {}})

    if "add_channel_step" in context.user_data:
        step = context.user_data["add_channel_step"]
        if step == 1:
            channel = text.strip()
            if not channel.startswith("@"):
                await update.message.reply_text("❌ Invalid channel format. Please enter a valid channel username starting with @.")
                return

            try:
                if "channels" not in data[user_id]:
                    data[user_id]["channels"] = []
                if channel not in data[user_id]["channels"]:
                    data[user_id]["channels"].append(channel)
                    save_data(data)
                context.user_data.pop("add_channel_step")
                await update.message.reply_text(
                    f"✅ Channel {channel} added successfully!\n\n"
                    "Note: The bot must be added as an admin to monitor posts."
                )
            except Exception as e:
                await update.message.reply_text(f"❌ Error adding channel: {str(e)}")

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
                data[user_id]["api"] = {
                    "url": context.user_data["api_url"],
                    "key": context.user_data["api_key"],
                    "service": context.user_data["service_id"],
                    "quantity": quantity
                }
                save_data(data)
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
        
        data[user_id]["api"][editing] = value
        save_data(data)
        
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
                api = data[user_id].get("api")
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
    """Automatically detect new channel posts and send to SMM panel."""
    if not update.channel_post:
        return

    chat = update.channel_post.chat
    message_id = update.channel_post.message_id

    if not chat.username:
        return  # Skip private channels

    channel_mention = f"@{chat.username}"
    post_link = f"https://t.me/{chat.username}/{message_id}"

    data = load_data()
    for user_id, user_data in data.items():
        if not user_data.get("channels") or not user_data.get("api"):
            continue

        if channel_mention not in user_data["channels"]:
            continue

        api = user_data["api"]
        quantity = api.get("quantity", 1000)

        try:
            response = requests.post(api['url'], data={
                "key": api['key'],
                "action": "add",
                "service": api['service'],
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
                                 f"📢 Channel: {channel_mention}\n"
                                 f"🔗 Post: {post_link}\n"
                                 f"📈 Views: {quantity}\n"
                                 f"🆔 Order ID: {res['order']}\n"
                                 f"💰 Estimated Cost: {res.get('price', 'Unknown')}"
                        )
                    except Exception as e:
                        print(f"Couldn't notify user {user_id}: {str(e)}")
        except Exception as e:
            print(f"Error processing {post_link}: {str(e)}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Handle user messages (skip channel posts)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.ChatType.CHANNEL,
        message_handler
    ))
    
    # Handle channel posts separately
    app.add_handler(MessageHandler(
        filters.ChatType.CHANNEL,
        handle_new_channel_post
    ))
    
    app.run_polling()
