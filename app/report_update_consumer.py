import base64
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_tz, mktime_tz

from googleapiclient.errors import HttpError

from biz.dal.user import Account
from biz.model.report.report_update_message import report_update_message_from_dict
from biz.service.db import get_session, init_db
from biz.service.sqs import get_sqs_client, init_sqs
from biz.utils.env import RuntimeEnv
from biz.utils.gmail import build_gmail_client
from biz.utils.logger import logger


class GmailInfo:
    snippet: str
    mime_type: str
    date: datetime
    sender_name: str
    sender_email: str
    subject: str
    body: str

    def __init__(self):
        pass


def extract_gmail_info(email_info):
    snippet = email_info["snippet"]
    payload = email_info["payload"]
    headers = payload["headers"]
    extracted_gmail_info = GmailInfo()
    extracted_gmail_info.snippet = snippet
    extracted_gmail_info.mime_type = payload["mimeType"]
    for header in headers:
        if header["name"] == "Date":
            raw_date = header["value"]
            parsed_time = parsedate_tz(raw_date)
            extracted_gmail_info.date = datetime.fromtimestamp(mktime_tz(parsed_time), timezone.utc)
        elif header["name"] == "From":
            match = re.match(r"(.+?)\s*<(.+?)>", header['value'])
            if match:
                extracted_gmail_info.sender_name = match.group(1).strip()
                extracted_gmail_info.sender_email = match.group(2).strip()
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


def handle_message(message_body):
    report_update_message = report_update_message_from_dict(message_body)

    if report_update_message.messages.gmail:  # handle gmail messages
        gmail_account_info = report_update_message.messages.gmail.account_info
        new_gmail_messages = report_update_message.messages.gmail.new_messages

        # get user account info from db
        with get_session(False) as session:
            account_info = Account.get_by_provider_and_provider_id(
                session,
                gmail_account_info.provider,
                gmail_account_info.provider_account_id
            )

        # use user account info to call gmail api
        gmail_api_client, _ = build_gmail_client(
            account_info.access_token,
            account_info.refresh_token,
            datetime.fromtimestamp(account_info.expires_at)
        )

        for new_gmail_msg in new_gmail_messages:
            try:
                email_info = gmail_api_client.users().messages().get(
                    userId="me",
                    id=new_gmail_msg.message_id,
                ).execute()

                # use llm process email info
                extracted_gmail_info = extract_gmail_info(email_info)
                print(extracted_gmail_info)
            except HttpError as e:
                if e.resp.status == 404:
                    logger.warning(f"Message not found: {new_gmail_msg.message_id}")
                    continue


def init():
    init_db()
    init_sqs()


if __name__ == '__main__':
    init()
    logger.info('Agent service starting up...')
    try:
        while True:
            response = get_sqs_client().receive_message(
                QueueUrl=RuntimeEnv.Instance().SQS_REPORT_UPDATE_QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=10,  # long pooling
            )

            messages = response.get('Messages', [])
            if not messages:
                logger.debug("No messages received, continuing...")
                continue

            for message in messages:
                logger.info(f"Received message: {message['MessageId']}")

                if not message.get('Body'):
                    logger.warning(f"Received message: {message['MessageId']} without body")
                    # ACK message
                    get_sqs_client().delete_message(
                        QueueUrl=RuntimeEnv.Instance().SQS_REPORT_UPDATE_QUEUE_URL,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                    continue

                try:
                    handle_message(json.loads(message['Body']))
                except Exception as e:
                    logger.error(f"Error processing message: {message['MessageId']}, error: {e}")
                    continue

                # ACK message
                get_sqs_client().delete_message(
                    QueueUrl=RuntimeEnv.Instance().SQS_REPORT_UPDATE_QUEUE_URL,
                    ReceiptHandle=message['ReceiptHandle']
                )
                logger.info(f"Successfully ACK message: {message['MessageId']}")
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}")
