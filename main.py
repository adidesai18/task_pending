from flask import Flask
from threading import Thread
from telegram.ext import run_async
from datetime import timedelta, datetime,time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler, ConversationHandler, MessageHandler, Filters
from telegram import Update
import firebase_admin
from firebase_admin import credentials, firestore
import os
import pytz  # For time zone conversion

app = Flask(__name__)

@app.route("/health")
def health_check():
    return "OK", 200    

def run_flask_app():
    app.run(host="0.0.0.0", port=8080)

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

# # Initialize a simple cache for storing tasks
# tasks_cache = {}

# Constants for states in the conversation handler
TASK, GENERAL_TASK = range(2)

@run_async
def show_tasks(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    # print(chat_id)
    # print(tasks_cache)
    # if chat_id in tasks_cache:
    #     keyboard = [
    #         [InlineKeyboardButton("Tomorrow", callback_data='show_tasks_tomorrow'),
    #         InlineKeyboardButton("Other", callback_data='show_tasks_other')]
    #     ]

    #     reply_markup = InlineKeyboardMarkup(keyboard)
    #     update.message.reply_text(tasks_cache[chat_id], reply_markup=reply_markup, parse_mode='Markdown')
    #     # Create InlineKeyboardButtons for "Tomorrow" and "Other"
        
    #     return

    ist = pytz.timezone('Asia/Kolkata')
    tasks_ref = db.collection("tasks").document(str(chat_id)).collection("user_tasks")
    
    # Modify query to only select tasks for today
    today_morning = datetime.combine(datetime.now(ist).date(), time(0, 0)).astimezone(ist)
    today_night = datetime.combine(datetime.now(ist).date(), time(23, 59)).astimezone(ist)
    tasks = tasks_ref.where("status", "==", "pending").where("next_reminder_time", ">=", today_morning).where("next_reminder_time", "<", today_night).limit(15).stream()

    message_text = "*Pending Tasks for Today:*\n\n"

    task_list = []
    for task in tasks:
        task_data = task.to_dict()
        
        # Only append the task name, omitting the schedule info
        task_list.append(f"*{task_data['task']}*")

    message_text += "\n".join(task_list) if task_list else "No pending tasks for today."

    # Create InlineKeyboardButtons for "Tomorrow" and "Other"
    keyboard = [
        [InlineKeyboardButton("Tomorrow", callback_data='show_tasks_tomorrow'),
         InlineKeyboardButton("Other", callback_data='show_tasks_other')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # # Cache the result before sending it
    # tasks_cache[chat_id] = message_text

    update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

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
        print(chat_id)
        current_time = datetime.now(pytz.timezone('Asia/Kolkata'))
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
        batch.commit()
        
        # # Invalidate cache for this chat_id
        # if chat_id in tasks_cache:
        #     del tasks_cache[chat_id]
        
        update.message.reply_text(f"Task added: {task_text}. Reminders set.")
        return ConversationHandler.END
    
    except Exception as e:
        update.message.reply_text(f"An error occurred: {str(e)}")
        return ConversationHandler.END

@run_async
def button(update: Update, context: CallbackContext):
    try:
        query = update.callback_query
        action_data = query.data.split('_')
        action = action_data[0]

        ist = pytz.timezone('Asia/Kolkata')
        chat_id = query.message.chat_id
        tasks_ref = db.collection("tasks").document(str(chat_id)).collection("user_tasks")

        if action in ["show","tasks", "tomorrow","other","today"]:
            tasks = None
            if query.data == "show_tasks_tomorrow":
                message_text = "*Pending Tasks for Tomorrow:*\n\n"
                tomorrow_date = datetime.now(ist).date() + timedelta(days=1)
                tomorrow_morning= datetime.combine(tomorrow_date, time(0, 0)).astimezone(ist)
                tomorrow_night= datetime.combine(tomorrow_date, time(23, 59)).astimezone(ist)
                tasks = tasks_ref.where("status", "==", "pending").where("next_reminder_time", ">=", tomorrow_morning).where("next_reminder_time", "<", tomorrow_night).limit(15).stream()

            elif query.data == "show_tasks_other":
                query.edit_message_text("Please provide the date in DD:MM:YY format.")
                # Further code needed to handle user response and show tasks for that date
                return

            elif query.data == "show_tasks_today":
                message_text = "*Pending Tasks for Today:*\n\n"
                today_morning = datetime.combine(datetime.now(ist).date(), time(0, 0)).astimezone(ist)
                today_night = datetime.combine(datetime.now(ist).date(), time(23, 59)).astimezone(ist)
                tasks = tasks_ref.where("status", "==", "pending").where("next_reminder_time", ">=", today_morning).where("next_reminder_time", "<", today_night).limit(15).stream()
            
           
            task_list = []
            for task in tasks:
                task_data = task.to_dict()
                task_list.append(f"*{task_data['task']}*")

            message_text += "\n".join(task_list) if task_list else "No pending tasks for today."

            keyboard = [
                [InlineKeyboardButton("Today", callback_data='show_tasks_today') 
                 if query.data == "show_tasks_tomorrow" 
                 else InlineKeyboardButton("Tomorrow", callback_data='show_tasks_tomorrow'),
                InlineKeyboardButton("Other", callback_data='show_tasks_other')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

        elif action in ["complete", "pending"]:
            task_ref_id = action_data[1]
            task_ref = tasks_ref.document(task_ref_id)
            task_ref.update({"status": action})
            button_text = "Task Completed ✅" if action == "complete" else "Task Pending ⏳"
            new_keyboard = [[InlineKeyboardButton(button_text, callback_data=f"none_{task_ref_id}")]]
            reply_markup = InlineKeyboardMarkup(new_keyboard)
            query.edit_message_reply_markup(reply_markup)
            query.edit_message_text(f"Task status set to {action}.")

            # # Invalidate cache for this chat_id
            # if chat_id in tasks_cache:
            #     del tasks_cache[chat_id]
        else:
            query.edit_message_text("Invalid action.")

    except Exception as e:
        query.edit_message_text(f"An error occurred: {str(e)}")

@run_async
def status_command(update: Update, context: CallbackContext):
    try:
        chat_id = update.message.chat_id
        tasks_ref = db.collection("tasks").document(str(chat_id)).collection("user_tasks")
        ist = pytz.timezone('Asia/Kolkata')
        today_morning = datetime.combine(datetime.now(ist).date(), time(0, 0)).astimezone(ist)
        today_night = datetime.combine(datetime.now(ist).date(), time(23, 59)).astimezone(ist)
        tasks = tasks_ref.where("status", "==", "pending").where("next_reminder_time", ">=", today_morning).where("next_reminder_time", "<", today_night).limit(15).stream()
        keyboard = []
        index = 1

        for task in tasks:
            task_data = task.to_dict()
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
        
        # # Invalidate or update cache for this chat_id, if applicable
        # if chat_id in tasks_cache:
        #     del tasks_cache[chat_id]

    except Exception as e:
        print("Hello")
        update.message.reply_text(f"An error occurred: {str(e)}")

# Function to encapsulate time details
def get_time_details(time_zone: str):
    ist = pytz.timezone(time_zone)
    current_time = datetime.now(ist)
    future_time_limit = current_time + timedelta(hours=24)
    return ist, current_time, future_time_limit

@run_async
def add_general_task(update: Update, context: CallbackContext):
    update.message.reply_text("Please enter the general task for today.")
    return GENERAL_TASK

@run_async
def set_general_task(update: Update, context: CallbackContext):
    try:
        task_text = update.message.text.strip()
        if not task_text:
            update.message.reply_text("Task text cannot be empty.")
            return ConversationHandler.END

        chat_id = update.message.chat_id
        ist = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(ist)
        
        # Set the reminder time to the end of the current day
        end_of_day = datetime(current_time.year, current_time.month, current_time.day, 23, 59, 59, tzinfo=ist)
        
        task_ref = db.collection("tasks").document(str(chat_id)).collection("user_tasks").document()
        task_ref.set({
            "task": task_text,
            "added": current_time,
            "status": "pending",
            "next_reminder_time": end_of_day
        })

        # # Invalidate cache for this chat_id
        # if chat_id in tasks_cache:
        #     del tasks_cache[chat_id]

        update.message.reply_text(f"General task added for today: {task_text}.")
        return ConversationHandler.END
    except Exception as e:
        update.message.reply_text(f"An error occurred: {str(e)}")
        return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[
        CommandHandler('add', add_task),
        CommandHandler('generaltask', add_general_task)  # Changed this line
    ],
    states={
        TASK: [MessageHandler(Filters.text & ~Filters.command, set_reminder)],
        GENERAL_TASK: [MessageHandler(Filters.text & ~Filters.command, set_general_task)]
    },
    fallbacks=[],
)

# Add handlers
dispatcher.add_handler(CommandHandler('show', show_tasks))
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(CommandHandler('status', status_command))
dispatcher.add_handler(conv_handler)

if __name__ == "__main__":
    t = Thread(target=run_flask_app)
    t.start()

    # Start the Telegram bot
    updater.start_polling()