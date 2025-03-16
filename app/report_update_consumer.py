import json
from datetime import datetime

from googleapiclient.errors import HttpError

from biz.controller import report_update as report_update_ctrl
from biz.controller.gmail_util import RawGmailInfo
from biz.dal.user import Account
from biz.model.report.report_update_message import report_update_message_from_dict, ReportUpdateMessage
from biz.service.db import get_session, init_db
from biz.service.sqs import get_sqs_client, init_sqs
from biz.utils.env import RuntimeEnv
from biz.utils.gmail import build_gmail_client
from biz.utils.logger import logger


def handle_message(report_update_message: ReportUpdateMessage):
    if report_update_message.messages.gmail:  # handle gmail messages
        gmail_account_info = report_update_message.messages.gmail.account_info
        new_gmail_messages = report_update_message.messages.gmail.new_messages

        # get user account info from db
        with get_session(False) as session:
            account = Account.get_by_id(session, gmail_account_info.account_id)

        # use user account info to call gmail api
        gmail_api_client, _ = build_gmail_client(
            account.access_token,
            account.refresh_token,
            datetime.fromtimestamp(account.expires_at)
        )

        emails = []
        for new_gmail_msg in new_gmail_messages:
            try:
                email_info = gmail_api_client.users().messages().get(
                    userId="me",
                    id=new_gmail_msg.message_id,
                ).execute()
                emails.append(RawGmailInfo(new_gmail_msg.message_id, new_gmail_msg.thread_id, email_info))
            except HttpError as e:
                if e.resp.status == 404:
                    logger.warning(f"Message not found: {new_gmail_msg.message_id}")
                    continue

        # use llm process email info
        report_update_ctrl.update_report_with_gmail_message(
            report_update_message.user_info.user_id,
            str(gmail_account_info.account_id),
            account.email,
            report_update_message.report_info.report_id,
            emails,
        )


def init():
    init_db()
    init_sqs()


if __name__ == '__main__':
    logger.info('Agent service starting up...')
    init()
    logger.info('Agent service start consuming')
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
                    handle_message(report_update_message_from_dict(json.loads(message['Body'])))
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
