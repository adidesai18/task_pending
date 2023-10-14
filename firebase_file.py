import firebase_admin
from firebase_admin import credentials, firestore
from datetime import timedelta, datetime,time
from google.api_core.datetime_helpers import DatetimeWithNanoseconds
import pytz
import os

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
ist = pytz.timezone('Asia/Kolkata')

class Firebase_Class:
    # Initialize the attributes
    def __init__(self):
        self.cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(self.cred)
        self.db = firestore.client()

    def ref_db(self):
        return self.db

    def ref_user_tasks_db(self,chat_id):
        return self.db.collection("tasks").document(str(chat_id)).collection("user_tasks")

    def get_day_data(self,chat_id,increment_days,hour_1,minute_1,hour_2,minute_2):
        tasks = self.ref_user_tasks_db(chat_id).where("next_reminder_time", ">=", self.time_obj(hour_1,minute_1,increment_days)).where("next_reminder_time", "<=", self.time_obj(hour_2,minute_2,increment_days)).limit(15).stream()
        return tasks
    
    def escape_markdown_v2(self,text: str) -> str:
        escape_chars = r'_*[]()~`>#+-=|{}.!'
        return ''.join('\\' + char if char in escape_chars else char for char in text)
    
    
    
    def get_display_text(self,tasks,empty_list:list,message_text:str):
        for task in tasks:
            task_data = task.to_dict()
            if 'category' in task_data and task_data['category']=="general":
                task_text = self.escape_markdown_v2(f"{task_data['task']} ({self.days_diff(task_data['next_reminder_time'],task_data['added'])})")
                if task_data['status']=="complete":
                    print("~{task_text}~")
                    empty_list.append(f"~{task_text}~")
                else:
                    empty_list.append(f"{task_text}")
            else:
                task_simple_text = f"{task_data['task']}"
                if task_data['status']=="complete":
                    empty_list.append(f"~{task_simple_text}~")
                else:
                    empty_list.append(f"{task_simple_text}")
        if empty_list:
            message_text += "\n".join(empty_list)
        else:
            message_text="No pending tasks for today"
        return message_text
    
    def convert_to_google_datetime(self,standard_dt: datetime) -> DatetimeWithNanoseconds:
        return DatetimeWithNanoseconds(
            standard_dt.year, standard_dt.month, standard_dt.day,
            standard_dt.hour, standard_dt.minute, standard_dt.second,
            standard_dt.microsecond, tzinfo=standard_dt.tzinfo
        )
        
    def time_obj(self,t1,t2,d):
        dt_obj = datetime.combine(datetime.now(ist).date() + timedelta(days=d), time(t1, t2)).astimezone(ist)
        return self.convert_to_google_datetime(dt_obj)
    
    def convt_gdt_sdt(self,google_datetime):
        # google.api_core.datetime_helpers.DatetimeWithNanoseconds
        dt_standard = datetime.fromtimestamp(google_datetime.timestamp()).replace(tzinfo=google_datetime.tzinfo)
        # datetime.datetime
        return dt_standard
    
    def crn_dt_obj(self):
        '''Convert Google DateTime to Standard DateTime'''
        return datetime.now(ist)
    
    def day_spec_fb_data(self,id,inc):
        return self.get_day_data(id,inc,0,0,23,59)
    
    def days_diff(self, t1, t2):
        diff = int((self.convt_gdt_sdt(t1).day - self.convt_gdt_sdt(t2).day))
        special_cases = {
            0: 1,
            -1: 1,
            3: 2,
            6: 3,
            14: 4,
            29: 5
        }
        return special_cases.get(diff, diff)