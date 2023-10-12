from flask import Flask
from threading import Thread
from telegram.ext import run_async
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler, ConversationHandler, MessageHandler, Filters
from telegram import Update
import os
from firebase_file import Firebase_Class
from time import sleep
import requests
from threading import Thread

app = Flask(__name__)

@app.route("/health")
def health_check():
    return "OK", 200    

def run_flask_app():
    app.run(host="0.0.0.0", port=8080)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Initialize Firestore
fire=Firebase_Class()


# Initialize Telegram Bot
updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

# # Initialize a simple cache for storing tasks
# tasks_cache = {}

# Constants for states in the conversation handler
TASK, GENERAL_TASK = range(2)

def check_health():
    while True:
        response = requests.get("http://localhost:8080/health")
        if response.status_code == 200:
            print("Health check OK")
        else:
            print("Health check failed")
        sleep(60)  # Sleep for 3 minutes (180 seconds)


@run_async
def show_tasks(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    tasks=fire.get_day_data(chat_id,0,0,0,23,59)
    message_text = "*Pending tasks for today:*\n\n"
    pending_task_list=[]
    for task in tasks:
        task_data = task.to_dict()
        if 'category' in task_data and task_data['category']=="general":
            task_text=f"{task_data['task']}"+f" ({fire.days_diff(task_data['next_reminder_time'],task_data['added'])})"
            pending_task_list.append(f"*{task_text}*")
        else:
            pending_task_list.append(f"{task_data['task']}")
    if pending_task_list:
        message_text += "\n".join(pending_task_list)
    else:
        message_text="No pending tasks for today"
    # Create InlineKeyboardButtons for "Tomorrow" and "Other"
    keyboard = [
        [InlineKeyboardButton("Tomorrow", callback_data='show_tasks_tomorrow'),
         InlineKeyboardButton("Other", callback_data='show_tasks_other')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # # Cache the result before sending it
    # tasks_cache[chat_id] = message_text
    update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

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
        batch = fire.ref_db().batch()
        for days in [0, 3, 7, 15, 30]:
            task_ref = fire.ref_user_tasks_db(chat_id).document()
            batch.set(task_ref, {
                "task": task_text,
                "added": fire.crn_dt_obj(),
                "category":'general',
                "status": "pending",
                "next_reminder_time": fire.time_obj(fire.crn_dt_obj().hour,fire.crn_dt_obj().minute,days)
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
        chat_id = query.message.chat_id

        if action in ["show","tasks", "tomorrow","other","today"]:
            pending_task_list=[]
            day='today'
            if query.data == "show_tasks_tomorrow":
                day='tomorrow'
                tasks=fire.get_day_data(chat_id,1,0,0,23,59)

            elif query.data == "show_tasks_other":
                query.edit_message_text("Please provide the date in DD:MM:YY format.")
                return
            elif query.data == "show_tasks_today":
                tasks=fire.get_day_data(chat_id,0,0,0,23,59)
            message_text = f"*Pending tasks for {day}:*\n\n"
            for task in tasks:
                task_data = task.to_dict()
                if 'category' in task_data and task_data['category']=="specific":
                    pending_task_list.append(f"{task_data['task']}")
                else:
                    task_text=f"{task_data['task']}"+f" ({fire.days_diff(task_data['next_reminder_time'],task_data['added'])})"
                    pending_task_list.append(f"{task_text}")

            if pending_task_list:
                message_text += "\n".join(pending_task_list)
            else:
                if query.data == "show_tasks_today":
                    message_text="*No pending tasks for today*"
                else:
                    message_text="*No pending tasks for tomorrow*"

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
            task_ref = fire.ref_user_tasks_db(chat_id).document(task_ref_id)
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
        tasks=fire.get_day_data(chat_id,0,0,0,23,59)
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
        
        task_ref = fire.ref_user_tasks_db(chat_id).document()
        task_ref.set({
            "task": task_text,
            "added": fire.crn_dt_obj(),
            "status": "pending",
            "category":"specific",
            "next_reminder_time": fire.time_obj(23,59,0)
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
    # Start Flask app in a separate thread
    flask_thread = Thread(target=run_flask_app)
    flask_thread.start()

    # Start health check in a separate thread
    health_check_thread = Thread(target=check_health)
    health_check_thread.start()

    # Start the Telegram bot
    updater.start_polling()
