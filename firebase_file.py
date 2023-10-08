import firebase_admin
from firebase_admin import credentials, firestore
from datetime import timedelta, datetime,time
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
        tasks = self.ref_user_tasks_db(chat_id).where("status", "==", "pending").where("next_reminder_time", ">=", self.time_obj(hour_1,minute_1,increment_days)).where("next_reminder_time", "<=", self.time_obj(hour_2,minute_2,increment_days)).limit(15).stream()
        return tasks
        
    def time_obj(self,t1,t2,d):
        dt_obj = datetime.combine(datetime.now(ist).date() + timedelta(days=d), time(t1, t2)).astimezone(ist)
        return dt_obj
    
    def crn_dt_obj(self):
        return datetime.now(ist)