from datetime import datetime, timezone
from enum import Enum


class EmailBodyType(str, Enum):
    Text = "text/plain"
    Html = "text/html"


class ExtractedMail:
    def __init__(self):
        self.message_id = ""
        self.thread_id = ""
        self.mime_type = ""
        self.receive_at = datetime.now(timezone.utc)
        self.sender = "" # sender that contains name and email in the form of "{sender_name} <{sender_email}>"
        self.sender_name = ""
        self.sender_email = ""
        self.to = ""
        self.subject = ""
        self.body = ""