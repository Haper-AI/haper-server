import base64
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.utils import parsedate_tz, mktime_tz
from typing import List

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from biz.controller.mail_util_base import ExtractedMail, EmailBodyType
from biz.utils import split_email_str, extract_visible_text_from_email
from biz.utils.env import RuntimeEnv
from biz.model.report import report_update_message as rum_model
from biz.utils.logger import logger


class RawGmailInfo:
    def __init__(self, message_id: str, thread_id: str, raw_email: dict):
        self.message_id = message_id
        self.thread_id = thread_id
        self.raw_email = raw_email


class GmailInfo(ExtractedMail):
    def __init__(self):
        super().__init__()
        self.marked_promotion = False
        self.snippet = ""


# recursively parse gmail body
def extract_body_from_payload(payload):
    mime_type = payload.get("mimeType", "")
    body = None
    body_type = None

    if mime_type in ["text/plain", "text/html"]:
        if "data" in payload.get("body", {}):
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
            body_type = EmailBodyType(mime_type)

    elif mime_type.startswith("multipart/"):  # handle multipart emails
        for part in payload.get("parts", []):
            part_body, part_body_type = extract_body_from_payload(part)

            # Prefer HTML content if available
            if part_body_type == EmailBodyType.Html:
                body = part_body
                body_type = part_body_type
                return body, body_type

            # Use the first found text content if no HTML content found yet
            elif part_body_type == EmailBodyType.Text and not body:
                body = part_body
                body_type = part_body_type

    return body, body_type


def extract_gmail_info(email_info: dict, message_id: str = "", thread_id: str = "", clean_html=True) -> GmailInfo:
    label_ids = email_info["labelIds"]
    snippet = email_info["snippet"]
    payload = email_info["payload"]
    headers = payload["headers"]
    extracted_gmail_info = GmailInfo()
    if message_id:
        extracted_gmail_info.message_id = message_id
    if thread_id:
        extracted_gmail_info.thread_id = thread_id
    extracted_gmail_info.marked_promotion = "CATEGORY_PROMOTION" in label_ids
    extracted_gmail_info.snippet = snippet
    for header in headers:
        if header["name"] == "Date":
            raw_date = header["value"]
            parsed_time = parsedate_tz(raw_date)
            extracted_gmail_info.receive_at = datetime.fromtimestamp(mktime_tz(parsed_time), timezone.utc)
        elif header["name"] == "From":
            extracted_gmail_info.sender = header["value"]
            sender_name, sender_email = split_email_str(header["value"])
            extracted_gmail_info.sender_name = sender_name
            extracted_gmail_info.sender_email = sender_email
        elif header["name"] == "To" or header["name"] == "to":
            extracted_gmail_info.to = header["value"]
        elif header["name"] == "Subject":
            extracted_gmail_info.subject = header['value']

    # get email body
    body, body_type = extract_body_from_payload(payload)
    if not body:
        logger.warning("no data found in payload body, payload body is {}".format(payload["body"]))

    extracted_gmail_info.body = body
    extracted_gmail_info.mime_type = body_type
    if body_type == EmailBodyType.Html and clean_html:
        extracted_gmail_info.cleaned_body = extract_visible_text_from_email(body)
    else:
        extracted_gmail_info.cleaned_body = body

    return extracted_gmail_info


class GmailAPIClient:
    def __init__(self, access_token: str, refresh_token: str, expires_at: int):
        self.credential = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            expiry=datetime.fromtimestamp(expires_at),
            token_uri="https://accounts.google.com/o/oauth2/token",
            client_id=RuntimeEnv.Instance().GOOGLE_CLIENT_ID,
            client_secret=RuntimeEnv.Instance().GOOGLE_CLIENT_SECRET
        )
        self.client = build('gmail', 'v1', credentials=self.credential)

    @property
    def access_token(self) -> str:
        return self.credential.token

    @property
    def expires_at(self) -> int:
        return int(self.credential.expiry.timestamp())

    def watch_gmail(self):
        gmail_watch_resp = self.client.users().watch(
            userId='me',
            body={
                'topicName': RuntimeEnv.Instance().GMAIL_WATCH_PUB_SUB_TOPIC,
                'labelIds': ['INBOX'],
                'labelFilterBehavior': 'INCLUDE'
            }
        ).execute()
        history_id = gmail_watch_resp.get('historyId')
        expiration = int(gmail_watch_resp.get('expiration')) // 1000
        return history_id, expiration

    def stop_watch(self):
        self.client.users().stop(userId='me').execute()

    def list_new_mails(self, pre_history_id: int, cur_history_id: int):
        has_next_page = True
        page_token = None
        new_gmail_message: List[rum_model.GmailNewMessage] = []

        while has_next_page:
            response = self.client.users().history().list(
                userId="me",
                startHistoryId=pre_history_id,
                pageToken=page_token,
                historyTypes=["messageAdded"]  # Only get added message only right now.
            ).execute()

            for history in response.get('history', []):
                if int(history["id"]) <= cur_history_id:  # only get message range in [pre_history_id, cur_history_id]
                    if "messagesAdded" in history:
                        for message in history['messagesAdded']:
                            new_gmail_message.append(rum_model.GmailNewMessage(
                                message_id=message["message"]["id"],
                                thread_id=message["message"]["threadId"],
                            ))
                else:
                    has_next_page = False
                    break
            page_token = response.get("nextPageToken")
            has_next_page = has_next_page and page_token is not None

        return new_gmail_message

    def get_email(self, message_id: str):
        return self.client.users().messages().get(userId="me", id=message_id).execute()

    def read_email(self, message_id: str):
        self.client.users().messages().modify(
            userId='me',
            id=message_id,
            body={
                'removeLabelIds': ['UNREAD'],
            }
        ).execute()

    def trash_email(self, message_id: str):
        self.client.users().messages().trash(
            userId='me',
            id=message_id,
        ).execute()

    def reply_email_text(self, recipient_address: str, thread_id: str, text_payload: str):
        message = MIMEText(text_payload)
        message['to'] = recipient_address
        message['from'] = 'me'
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        self.client.users().messages().send(
            userId='me',
            body={
                "threadId": thread_id,
                "raw": raw_message,
            }
        ).execute()
