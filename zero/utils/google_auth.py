from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import os

def get_credentials():
    token_path = os.path.expanduser("~/.zero/token.json")
    return Credentials.from_authorized_user_file(token_path)

def get_calendar_service():
    return build("calendar", "v3", credentials=get_credentials())

def get_gmail_service():
    return build("gmail", "v1", credentials=get_credentials())

def get_tasks_service():
    return build("tasks", "v3", credentials=get_credentials())
