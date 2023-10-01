import datetime
from datetime import timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler, ConversationHandler, MessageHandler, Filters
from telegram import Update
import firebase_admin
from firebase_admin import credentials, firestore
import os
import pytz  # For time zone conversion

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")

cred_dict = {
    "type": "service_account",
    "project_id": os.environ.get("FIREBASE_PROJECT_ID"),
    "private_key_id": os.environ.get("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.environ.get("FIREBASE_PRIVATE_KEY").replace('\\n', '\n'),
    "client_email": os.environ.get("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.environ.get("FIREBASE_CLIENT_ID"),
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url":  os.environ.get("FIREBASE_CLIENT_CERT_URL"),
    "universe_domain": "googleapis.com"
}

# Initialize Firestore
cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Initialize Telegram Bot
updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# Constants for states in the conversation handler
TASK = range(1)

# Modified show_tasks function
def show_tasks(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    tasks_ref = db.collection("tasks").document(str(chat_id)).collection("user_tasks")
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
    future_time_limit = current_time + timedelta(hours=24)

    tasks = tasks_ref.where("status", "==", "pending").stream()
    message_text = "*Pending Tasks for Next 24 Hours:*\n\n"

    task_list = []
    index = 1
    for task in tasks:
        task_data = task.to_dict()
        task_date_time = task_data['next_reminder_time'].astimezone(ist)

        if current_time <= task_date_time <= future_time_limit:
            formatted_date_time = task_date_time.strftime('%d-%m-%Y %I:%M %p')
            task_list.append(f"{index}. *{task_data['task']}*\n   Scheduled for: {formatted_date_time}")
            index += 1

    if not task_list:
        message_text += "No pending tasks."
    else:
        message_text += "\n".join(task_list)

    update.message.reply_text(message_text, parse_mode='Markdown')


# Function to add a task
def add_task(update: Update, context: CallbackContext):
    update.message.reply_text("Please enter the task to be reminded of.")
    return TASK

# Modified set_reminder function
def set_reminder(update: Update, context: CallbackContext):
    task_text = update.message.text
    chat_id = update.message.chat_id
    current_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
    
    for days in [1, 3, 7, 15, 30]:
        future_task_time = current_time + timedelta(days=days)
        task_ref = db.collection("tasks").document(str(chat_id)).collection("user_tasks").add({
            "task": task_text,
            "added": current_time,
            "status": "pending",
            "next_reminder_time": future_task_time
        })
        
        context.job_queue.run_once(
            reminder_callback,
            (future_task_time - current_time).seconds,
            context={"chat_id": chat_id, "task_ref": task_ref[1]}
        )
    
    update.message.reply_text(f"Task added: {task_text}. Reminders set.")
    return ConversationHandler.END

# Callback for the inline button
def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    task_ref_id = query.data.split('_')[1]
    action = query.data.split('_')[0]

    task_ref = db.collection("tasks").document(str(query.message.chat_id)).collection("user_tasks").document(task_ref_id)

    if action == "complete":
        task_ref.update({"status": "complete"})
        new_keyboard = [[InlineKeyboardButton("Task Completed ✅", callback_data=f"none_{task_ref_id}")]]
        reply_markup = InlineKeyboardMarkup(new_keyboard)
    elif action == "pending":
        task_ref.update({"status": "pending"})
        new_keyboard = [[InlineKeyboardButton("Task Pending ⏳", callback_data=f"none_{task_ref_id}")]]
        reply_markup = InlineKeyboardMarkup(new_keyboard)
    else:
        reply_markup = None

    if reply_markup:
        query.edit_message_reply_markup(reply_markup)
    query.edit_message_text(f"Task status set to {action}.")

def status_command(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    tasks_ref = db.collection("tasks").document(str(chat_id)).collection("user_tasks")
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
    future_time_limit = current_time + timedelta(hours=24)
    
    tasks = tasks_ref.where("status", "==", "pending").stream()
    keyboard = []
    index = 1

    for task in tasks:
        task_data = task.to_dict()
        task_date_time = task_data['next_reminder_time'].astimezone(ist)

        # If the next reminder time falls within the next 24 hours
        if current_time <= task_date_time <= future_time_limit:
            btn_text = f"{index}. {task_data['task']}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"none_{task.id}")])
            keyboard.append([
                InlineKeyboardButton("Completed", callback_data=f"complete_{task.id}"),
                InlineKeyboardButton("Pending", callback_data=f"pending_{task.id}")
            ])
            index += 1

    if keyboard:
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("Tasks for the next 24 hours:", reply_markup=reply_markup)
    else:
        update.message.reply_text("No tasks for the next 24 hours.")

# Callback function to remind the user
def reminder_callback(context: CallbackContext):
    job = context.job
    chat_id = job.context['chat_id']
    task_ref = db.collection("tasks").document(str(chat_id)).collection("user_tasks").document(job.context['task_ref'].id)
    
    task_data = task_ref.get().to_dict()
    
    if task_data['status'] == 'complete':
        # If task is already complete, send the Completed Task ✅ button
        keyboard = [[InlineKeyboardButton("Completed Task ✅", callback_data=f"completed_{task_ref.id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_message(chat_id, text=f"Reminder: {task_data['task']}", reply_markup=reply_markup)
        return
    
    # Only send reminders for today's pending tasks
    ist = pytz.timezone('Asia/Kolkata')
    current_date = datetime.datetime.now(ist).date()
    task_date = task_data['next_reminder_time'].astimezone(ist).date()
    if current_date != task_date:
        return
    
    keyboard = [[InlineKeyboardButton("Mark Complete", callback_data=f"complete_{task_ref.id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    context.bot.send_message(chat_id, text=f"Reminder: {task_data['task']}", reply_markup=reply_markup)
    
    context.job_queue.run_once(
        reminder_callback,
        30,  # Re-trigger reminder after 30 seconds if not marked complete
        context={"chat_id": chat_id, "task_ref": task_ref}
    )

# Add handlers
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('add', add_task)],
    states={
        TASK: [MessageHandler(Filters.text & ~Filters.command, set_reminder)]
    },
    fallbacks=[],
)

# Add handlers
dispatcher.add_handler(CommandHandler('show', show_tasks))
dispatcher.add_handler(conv_handler)
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(CommandHandler('status', status_command))

# Start the bot
updater.start_polling()