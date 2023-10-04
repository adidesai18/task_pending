from flask import Flask
from threading import Thread
from telegram.ext import run_async
from functools import lru_cache


app = Flask(__name__)

@app.route("/health")
def health_check():
    return "OK", 200    

def run_flask_app():
    app.run(host="0.0.0.0", port=8080)

from datetime import datetime, timedelta
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

# Initialize a simple cache for storing tasks
tasks_cache = {}

# Constants for states in the conversation handler
TASK, DATE = range(2)

@run_async
def show_tasks(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if chat_id in tasks_cache:
        update.message.reply_text(tasks_cache[chat_id], parse_mode='Markdown')
        return

    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now().astimezone(ist)
    current_date = current_time.date()
    future_time_limit = current_time + timedelta(hours=24)

    tasks_ref = db.collection("tasks").document(str(chat_id)).collection("user_tasks")
    
    # Convert the time to UTC as Firestore stores it in UTC
    tasks = tasks_ref.where("status", "==", "pending").where("next_reminder_time", "<=", future_time_limit.astimezone(pytz.UTC)).where("next_reminder_time", ">=", current_time).limit(10).stream()

    message_text = "*Pending Tasks for Next 24 Hours:*\n\n"

    task_list = []
    for task in tasks:
        task_data = task.to_dict()
        task_date_time = task_data['next_reminder_time'].astimezone(ist)
        task_date = task_date_time.date()
        
        if task_date == current_date:
            formatted_date_time = f"Today {task_date_time.strftime('%I:%M %p')}"
        elif task_date == current_date + timedelta(days=1):
            formatted_date_time = f"Tomorrow {task_date_time.strftime('%I:%M %p')}"
        else:
            formatted_date_time = task_date_time.strftime('%d-%m-%Y %I:%M %p')
            
        task_list.append(f"*{task_data['task']}*\n   Scheduled for: {formatted_date_time}")

    message_text += "\n".join(task_list) if task_list else "No pending tasks."

    tasks_cache[chat_id] = message_text  # Cache the result
    update.message.reply_text(message_text, parse_mode='Markdown')

# Function to add a task
@run_async
def add_task(update: Update, context: CallbackContext):
    update.message.reply_text("Please enter the task to be reminded of.")
    return TASK

@run_async
def set_reminder(update: Update, context: CallbackContext):
    try:
        task_text = update.message.text.strip()
        if not task_text:
            update.message.reply_text("Task text cannot be empty.")
            return ConversationHandler.END
        chat_id = update.message.chat_id
        current_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
        batch = db.batch()
        for days in [1, 3, 7, 15, 30]:
            future_task_time = current_time + timedelta(days=days)
            task_ref = db.collection("tasks").document(str(chat_id)).collection("user_tasks").document()
            batch.set(task_ref, {
                "task": task_text,
                "added": current_time,
                "status": "pending",
                "next_reminder_time": future_task_time
            })
            
            context.job_queue.run_once(
                reminder_callback,
                (future_task_time - current_time).seconds,
                context={"chat_id": chat_id, "task_ref": task_ref.id}  # Assuming task_ref.id gives the document ID
            )
        
        batch.commit()
        
        # Invalidate cache for this chat_id
        if chat_id in tasks_cache:
            del tasks_cache[chat_id]
        
        update.message.reply_text(f"Task added: {task_text}. Reminders set.")
        return ConversationHandler.END
    
    except Exception as e:
        update.message.reply_text(f"An error occurred: {str(e)}")
        return ConversationHandler.END

@run_async
def button(update: Update, context: CallbackContext):
    try:
        query = update.callback_query
        query.answer()

        action, task_ref_id = query.data.split('_')

        task_ref = db.collection("tasks").document(str(query.message.chat_id)).collection("user_tasks").document(task_ref_id)

        if action in ["complete", "pending"]:
            task_ref.update({"status": action})
            button_text = "Task Completed ✅" if action == "complete" else "Task Pending ⏳"
            new_keyboard = [[InlineKeyboardButton(button_text, callback_data=f"none_{task_ref_id}")]]
            reply_markup = InlineKeyboardMarkup(new_keyboard)
            query.edit_message_reply_markup(reply_markup)
            query.edit_message_text(f"Task status set to {action}.")

            # Invalidate cache for this chat_id
            if query.message.chat_id in tasks_cache:
                del tasks_cache[query.message.chat_id]

        else:
            query.edit_message_text("Invalid action.")

    except Exception as e:
        query.edit_message_text(f"An error occurred: {str(e)}")

@run_async
def status_command(update: Update, context: CallbackContext):
    try:
        chat_id = update.message.chat_id
        tasks_ref = db.collection("tasks").document(str(chat_id)).collection("user_tasks")

        # Time zone and time logic encapsulated in a function (consider reusing across functions)
        ist, current_time, future_time_limit = get_time_details('Asia/Kolkata')

        tasks = tasks_ref.where("status", "==", "pending").stream()
        keyboard = []
        index = 1

        for task in tasks:
            task_data = task.to_dict()
            task_date_time = task_data['next_reminder_time'].astimezone(ist)

            # Check for tasks within the next 24 hours
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
        
        # Invalidate or update cache for this chat_id, if applicable
        if chat_id in tasks_cache:
            del tasks_cache[chat_id]

    except Exception as e:
        update.message.reply_text(f"An error occurred: {str(e)}")

# Function to encapsulate time details
def get_time_details(time_zone: str):
    ist = pytz.timezone(time_zone)
    current_time = datetime.datetime.now(ist)
    future_time_limit = current_time + timedelta(hours=24)
    return ist, current_time, future_time_limit

# Function to ask for a date
@run_async
def ask_for_date(update: Update, context: CallbackContext):
    update.message.reply_text("Please enter the date in DD:MM:YYYY format.")
    return DATE

@run_async
def show_date_tasks(update: Update, context: CallbackContext):
    date_str = update.message.text
    try:
        date_object = datetime.datetime.strptime(date_str, "%d:%m:%Y").date()
    except ValueError:
        update.message.reply_text("Invalid date format. Please enter date in DD:MM:YYYY format.")
        return DATE  # Assuming DATE is a defined state in your conversation handler

    chat_id = update.message.chat_id
    tasks_ref = db.collection("tasks").document(str(chat_id)).collection("user_tasks")
    ist, _, _ = get_time_details('Asia/Kolkata')  # Reusing the function from previous example

    tasks = tasks_ref.stream()

    pending_task_list = []
    complete_task_list = []

    for task in tasks:
        task_data = task.to_dict()
        task_date_time = task_data['next_reminder_time'].astimezone(ist)
        added_date_time = task_data['added'].astimezone(ist)

        if task_date_time.date() == date_object:
            task_entry = generate_task_entry(task_data, task_date_time, added_date_time)
            if task_data['status'] == "pending":
                pending_task_list.append(task_entry)
            else:
                complete_task_list.append(task_entry)

    message_text = f"*Tasks for {date_str}:*\n"
    message_text += generate_message_text("Pending Tasks", pending_task_list)
    message_text += generate_message_text("Completed Tasks", complete_task_list)

    update.message.reply_text(message_text, parse_mode='Markdown')
    return ConversationHandler.END

# Helper function to generate task entry
def generate_task_entry(task_data, task_date_time, added_date_time):
    formatted_date_time = task_date_time.strftime('%d-%m-%Y %I:%M %p')
    revision_time = (task_date_time - added_date_time).days
    return f"*{task_data['task']}* - Scheduled for: {formatted_date_time} - Revision Time: {revision_time} days"

# Helper function to generate message text
def generate_message_text(section_title, task_list):
    if task_list:
        return f"\n*{section_title}:*\n" + "\n".join(task_list) + "\n"
    else:
        return f"\n*{section_title}:*\nNone\n"


@run_async
def reminder_callback(context: CallbackContext):
    job = context.job
    task_ref = db.collection("tasks").document(str(job.context['chat_id'])).collection("user_tasks").document(job.context['task_ref'])
    task_data = task_ref.get().to_dict()
    
    if task_data['status'] == 'complete':
        send_completed_message(context, job, task_ref.id, task_data['task'])
        return
    
    ist = pytz.timezone('Asia/Kolkata')
    if datetime.datetime.now(ist).date() != task_data['next_reminder_time'].astimezone(ist).date():
        return

    send_pending_message(context, job, task_ref.id, task_data['task'])
    context.job_queue.run_once(
        reminder_callback,
        30,  # Re-trigger reminder after 30 seconds if not marked complete
        context=job.context  # Reuse existing context
    )

def send_completed_message(context, job, task_ref_id, task_text):
    keyboard = [[InlineKeyboardButton("Completed Task ✅", callback_data=f"completed_{task_ref_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(job.context['chat_id'], text=f"Reminder: {task_text}", reply_markup=reply_markup)

def send_pending_message(context, job, task_ref_id, task_text):
    keyboard = [[InlineKeyboardButton("Mark Complete", callback_data=f"complete_{task_ref_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(job.context['chat_id'], text=f"Reminder: {task_text}", reply_markup=reply_markup)



# Add this in your states dictionary for your ConversationHandler
DATE = range(2, 3)  # Assuming you haven't used 2 as a state yet

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('add', add_task),
                  CommandHandler('date', ask_for_date)],  # Add this line
    states={
        TASK: [MessageHandler(Filters.text & ~Filters.command, set_reminder)],
        DATE: [MessageHandler(Filters.text & ~Filters.command, show_date_tasks)],  # Add this line
    },
    fallbacks=[],
)

# Add handlers
dispatcher.add_handler(CommandHandler('show', show_tasks))
dispatcher.add_handler(conv_handler)
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(CommandHandler('status', status_command))

if __name__ == "__main__":
    t = Thread(target=run_flask_app)
    t.start()

    # Start the Telegram bot
    updater.start_polling()