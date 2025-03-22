import base64
import re
from datetime import datetime, timezone
from email.utils import parsedate_tz, mktime_tz


class RawGmailInfo:
    def __init__(self, message_id: str, thread_id: str, raw_email: dict):
        self.message_id = message_id
        self.thread_id = thread_id
        self.raw_email = raw_email


class GmailInfo:
    marked_promotion: bool
    snippet: str
    mime_type: str
    receive_at: datetime
    sender: str # sender that contains name and email in the form of "{sender_name} <{sender_email}>"
    sender_name: str
    sender_email: str
    to: str
    subject: str
    body: str

    def __init__(self):
        pass


def extract_gmail_info(email_info: dict):
    label_ids = email_info["labelIds"]
    snippet = email_info["snippet"]
    payload = email_info["payload"]
    headers = payload["headers"]
    extracted_gmail_info = GmailInfo()
    extracted_gmail_info.marked_promotion = "CATEGORY_PROMOTION" in label_ids
    extracted_gmail_info.snippet = snippet
    extracted_gmail_info.mime_type = payload["mimeType"]
    for header in headers:
        if header["name"] == "Date":
            raw_date = header["value"]
            parsed_time = parsedate_tz(raw_date)
            extracted_gmail_info.receive_at = datetime.fromtimestamp(mktime_tz(parsed_time), timezone.utc)
        elif header["name"] == "From":
            extracted_gmail_info.sender = header["value"]
            match = re.match(r"(.+?)\s*<(.+?)>", header['value'])
            if match:
                extracted_gmail_info.sender_name = match.group(1).strip()
                extracted_gmail_info.sender_email = match.group(2).strip()
        elif header["name"] == "To":
            extracted_gmail_info.to = header["value"]
        elif header["name"] == "Subject":
            extracted_gmail_info.subject = header['value']

    # get email body
    body = ""
    if extracted_gmail_info.mime_type == 'multipart/alternative':
        parts = payload["parts"]
        # prefer html part first
        for part in parts:
            if part["mimeType"] == "text/html":
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                break

        # if not html part, default to use the first part
        if not body:
            body = base64.urlsafe_b64decode(parts[0]["body"]["data"]).decode("utf-8")

    elif extracted_gmail_info.mime_type == "text/plain" or extracted_gmail_info.mime_type == "text/html":
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")

    extracted_gmail_info.body = body

    return extracted_gmail_info