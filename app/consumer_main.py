import asyncio
import base64
import json
from datetime import datetime

from googleapiclient.errors import HttpError
from kiota_abstractions.api_error import APIError

from biz.controller import report_update as report_update_ctrl
from biz.controller.gmail_util import RawGmailInfo
from biz.dal.report import Report, MessageAction
from biz.dal.report_batch_action import MessageActionResult, ReportBatchAction, BatchActionRunStatus
from biz.dal.user import Account
from biz.model.report import sqs_message as sqs_message_model
from biz.model.report import report as report_model
from biz.model.report import action_log as action_log_model
from biz.model.report.report_batch_action_message import ReportBatchActionMessage
from biz.model.report.report_update_message import ReportUpdateMessage
from biz.service.db import get_session, init_db
from biz.service.aws.sqs import get_sqs_client, init_sqs
from biz.utils import track_haper_error
from biz.utils.env import RuntimeEnv
from biz.utils.gmail import build_gmail_client
from biz.utils.logger import logger
from biz.utils.microsoft import build_microsoft_graph_client


def handle_report_update(the_message: ReportUpdateMessage):
    if the_message.messages.gmail:  # handle gmail messages
        account_id = the_message.messages.gmail.account_id
        new_gmail_messages = the_message.messages.gmail.new_messages

        # get user account info from db
        with get_session(False) as session:
            account = Account.get_by_id(session, account_id)

        # use user account info to call gmail api
        gmail_api_client, _ = build_gmail_client(
            account.access_token,
            account.refresh_token,
            account.expires_at
        )

        # fetch emails
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
                    logger.warning(f"Gmail not found: {new_gmail_msg.message_id}")
                    continue

        # use llm process email info
        report_update_ctrl.update_report_with_gmail_message(
            the_message.user_id,
            str(account_id),
            account.email,
            the_message.report_id,
            emails,
        )
    elif the_message.messages.outlook:
        account_id = the_message.messages.outlook.account_id
        new_mail_ids = the_message.messages.outlook.new_messages

        # get user account info from db
        with get_session(False) as session:
            account = Account.get_by_id(session, account_id)

        # use user account info to call outlook api
        msgraph_api_client, credential = build_microsoft_graph_client(
            account.access_token,
            account.refresh_token,
            account.expires_at
        )

        # fetch emails
        emails = []
        for mail_id in new_mail_ids:
            try:
                result = asyncio.run(msgraph_api_client.me.messages.by_message_id(mail_id).get())
                emails.append(result)
            except APIError as e:
                if e.response_status_code == 404:
                    logger.warning(f"Outlook mail not found: {mail_id}")
                    continue

        if credential.access_token != account.access_token:
            with get_session(True) as session:
                Account.update(
                    session,
                    account.id,
                    credential.access_token,
                    refresh_token=credential.refresh_token,
                    expires_at=credential.expiry,
                )

        # use llm process email info
        report_update_ctrl.update_report_with_outlook_emails(
            the_message.user_id,
            str(account_id),
            account.email,
            the_message.report_id,
            emails,
        )


def handle_report_batch_action(the_message: ReportBatchActionMessage):
    with get_session(write=True) as session:
        report = Report.get_by_id(session, the_message.report_id)
        report_obj = report_model.report_from_dict(report.content)
        ReportBatchAction.update(session, the_message.run_id, BatchActionRunStatus.Ongoing)

    if report_obj.content.gmail:
        # apply gmail actions
        for messages_by_account in report_obj.content.gmail:
            if messages_by_account.messages:
                # get account
                with get_session(write=False) as session:
                    account = Account.get_by_id(session, messages_by_account.account_id)

                gmail_api_client, credential = build_gmail_client(
                    account.access_token,
                    account.refresh_token,
                    account.expires_at
                )

                for gmail_item in messages_by_account.messages:
                    try:
                        if gmail_item.action_result == MessageActionResult.Success:
                            # skip for already success action
                            continue

                        if gmail_item.action == MessageAction.Read:
                            gmail_api_client.users().messages().modify(
                                userId='me',
                                id=gmail_item.message_id,
                                body={
                                    'removeLabelIds': ['UNREAD'],
                                }
                            ).execute()
                        elif gmail_item.action == MessageAction.Delete:
                            gmail_api_client.users().messages().trash(
                                userId='me',
                                id=gmail_item.message_id,
                            ).execute()
                        elif gmail_item.action == MessageAction.Reply:
                            body_data = base64.urlsafe_b64encode(gmail_item.reply_message.encode("utf-8"))
                            gmail_api_client.users().messages().send(
                                userId='me',
                                body={
                                    "threadId": gmail_item.thread_id,
                                    "payload": {
                                        # TODO: support more type of mimeType
                                        "mimeType": "text/plain",
                                        "body": {
                                            "size": len(body_data),
                                            "data": body_data.decode("utf-8")
                                        }
                                    }
                                }
                            ).execute()

                        # if gmail_item.action == MessageAction.Ignore:
                        # ignore

                        gmail_item.action_result = MessageActionResult.Success
                        log_to_add = action_log_model.ActionLog(
                            at=int(datetime.now().timestamp()),
                            id=gmail_item.id,
                            message=f"{gmail_item.action} {gmail_item.sender} failed",
                        ).to_dict()

                    except Exception as e:
                        logger.error(e)
                        gmail_item.action_result = MessageActionResult.Error
                        log_to_add = action_log_model.ActionLog(
                            at=int(datetime.now().timestamp()),
                            id=gmail_item.id,
                            message=f"{gmail_item.action} {gmail_item.sender} failed",
                        ).to_dict()
                    finally:
                        with get_session(write=True) as session:
                            # insert action log
                            ReportBatchAction.append_logs(session, the_message.run_id, [
                                log_to_add,
                            ])
                            if gmail_item.action_result == MessageActionResult.Success:
                                ReportBatchAction.increase_success_actions(session, the_message.report_id)
                            else:
                                ReportBatchAction.increase_failed_actions(session, the_message.report_id)
                            # update content
                            Report.update_content_subfield(session, the_message.report_id, "content",
                                                           report_obj.content.to_dict())

    # set batch run status
    with get_session(write=True) as session:
        ReportBatchAction.update(session, the_message.report_id, status=BatchActionRunStatus.Done)


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
                QueueUrl=RuntimeEnv.Instance().SQS_REPORT_ASYNC_ACTION_QUEUE_URL,
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
                        QueueUrl=RuntimeEnv.Instance().SQS_REPORT_ASYNC_ACTION_QUEUE_URL,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                    continue

                try:
                    sqs_message_obj = sqs_message_model.sqs_message_from_dict(json.loads(message['Body']))
                    if sqs_message_obj.action_type == sqs_message_model.ActionType.REPORT_UPDATE:
                        handle_report_update(sqs_message_obj.report_update_message)
                    else:
                        handle_report_batch_action(sqs_message_obj.report_batch_action_message)
                except Exception as e:
                    file_name, line_number, func_name, text = track_haper_error(e)
                    logger.error(f"Error in {file_name}, line {line_number}, in {func_name}: {text}")
                    logger.error(f"Error processing message: {message['MessageId']}, error: {e}")
                    continue

                # ACK message
                get_sqs_client().delete_message(
                    QueueUrl=RuntimeEnv.Instance().SQS_REPORT_ASYNC_ACTION_QUEUE_URL,
                    ReceiptHandle=message['ReceiptHandle']
                )
                logger.info(f"Successfully ACK message: {message['MessageId']}")
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}")
