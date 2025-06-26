import json
from datetime import datetime

from googleapiclient.errors import HttpError
from kiota_abstractions.api_error import APIError

from biz.controller import report_update as report_update_ctrl
from biz.controller.gmail_util import RawGmailInfo, GmailAPIClient
from biz.controller.outlook_util import OutlookAPIClient
from biz.controller.report_util import initialize_report
from biz.dal.email import EmailSource
from biz.dal.report import Report, MessageAction, ReportStatus
from biz.dal.report_batch_action import MessageActionResult, ReportBatchAction, BatchActionRunStatus
from biz.dal.user import Account, AccountProvider
from biz.utils.report import ReportFieldName
from haper_script.schema_gen.python import sqs_message as sqs_message_model
from haper_script.schema_gen.python import report as report_model
from haper_script.schema_gen.python import action_log as action_log_model
from haper_script.schema_gen.python.report_batch_action_message import ReportBatchActionMessage
from haper_script.schema_gen.python.report_update_message import ReportUpdateMessage
from haper_script.schema_gen.python.previous_report_generate_message import PreviousReportGenerateMessage
from biz.service.db import get_session, init_db
from biz.service.aws.sqs import get_sqs_client, init_sqs
from biz.utils import track_haper_error, split_email_str
from biz.utils.env import RuntimeEnv
from biz.utils.logger import logger


def handle_report_update(the_message: ReportUpdateMessage):
    if the_message.messages.gmail:  # handle gmail messages
        account_id = the_message.messages.gmail.account_id
        new_gmail_messages = the_message.messages.gmail.new_messages

        # get user account info from db
        with get_session(False) as session:
            account = Account.get_by_id(session, account_id)

        # use user account info to call gmail api
        gmail_api_client = GmailAPIClient(account.access_token, account.refresh_token, account.expires_at)

        # fetch emails
        emails = []
        for new_gmail_msg in new_gmail_messages:
            try:
                email_info = gmail_api_client.get_email(new_gmail_msg.message_id)
                emails.append(RawGmailInfo(new_gmail_msg.message_id, new_gmail_msg.thread_id, email_info))
            except HttpError as e:
                if e.resp.status == 404:
                    logger.warning(f"Gmail not found: {new_gmail_msg.message_id} for email {account.email}")
                    continue

        # use llm process found email info
        report_update_ctrl.update_report_with_gmail_message(
            the_message.user_id,
            str(account_id),
            account.email,
            the_message.report_id,
            emails,
            len(new_gmail_messages)
        )
    elif the_message.messages.outlook:
        account_id = the_message.messages.outlook.account_id
        new_mail_ids = the_message.messages.outlook.new_messages

        # get user account info from db
        with get_session(False) as session:
            account = Account.get_by_id(session, account_id)

        # use user account info to call outlook api
        outlook_api_client = OutlookAPIClient(
            account.access_token,
            account.refresh_token,
            account.expires_at
        )

        # fetch emails
        emails = []
        for mail_id in new_mail_ids:
            try:
                result = outlook_api_client.get_email(mail_id)
                emails.append(result)
            except APIError as e:
                if e.response_status_code == 404:
                    logger.warning(f"Outlook mail not found: {mail_id} for email {account.email}")
                    continue

        # use llm process email info
        report_update_ctrl.update_report_with_outlook_emails(
            the_message.user_id,
            str(account_id),
            account.email,
            the_message.report_id,
            emails,
            len(new_mail_ids)
        )


def handle_report_batch_action(the_message: ReportBatchActionMessage):
    with get_session(write=True) as session:
        report = Report.get_by_id(session, the_message.report_id)
        report_obj = report_model.report_from_dict(report.content)
        ReportBatchAction.update(session, the_message.run_id, BatchActionRunStatus.Ongoing)

    # TODO: remove redundant code
    if report_obj.content.gmail:
        # apply gmail actions
        for messages_by_account in report_obj.content.gmail:
            if messages_by_account.messages:
                # get account
                with get_session(write=False) as session:
                    account = Account.get_by_id(session, messages_by_account.account_id)

                gmail_api_client = GmailAPIClient(account.access_token, account.refresh_token, account.expires_at)

                for gmail_item in messages_by_account.messages:
                    if gmail_item.action_result == MessageActionResult.Success:
                        # skip for already success action
                        continue
                    try:
                        if gmail_item.action == MessageAction.Read:
                            gmail_api_client.read_email(gmail_item.message_id)
                        elif gmail_item.action == MessageAction.Delete:
                            gmail_api_client.trash_email(gmail_item.message_id)
                        elif gmail_item.action == MessageAction.Reply:
                            _, recipient_address = split_email_str(gmail_item.sender)
                            gmail_api_client.reply_email_text(recipient_address, gmail_item.thread_id,
                                                              gmail_item.reply_message)
                        # elif gmail_item.action == MessageAction.Ignore:
                        # ignore

                        gmail_item.action_result = MessageActionResult.Success
                        log_to_add = action_log_model.ActionLog(
                            at=int(datetime.now().timestamp()),
                            id=gmail_item.id,
                            message=f"{gmail_item.action} {gmail_item.sender} succeed",
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
                                ReportBatchAction.increase_success_actions(session, the_message.run_id)
                            else:
                                ReportBatchAction.increase_failed_actions(session, the_message.run_id)
                            # update content
                            Report.update_content_subfield(session, the_message.report_id, "content",
                                                           report_obj.content.to_dict())

    if report_obj.content.outlook:
        for messages_by_account in report_obj.content.outlook:
            if messages_by_account.messages:
                # get account
                with get_session(write=False) as session:
                    account = Account.get_by_id(session, messages_by_account.account_id)

                outlook_api_client = OutlookAPIClient(
                    account.access_token,
                    account.refresh_token,
                    account.expires_at
                )

                for outlook_item in messages_by_account.messages:
                    if outlook_item.action_result == MessageActionResult.Success:
                        # skip for already success action
                        continue
                    try:
                        if outlook_item.action == MessageAction.Read:
                            outlook_api_client.read_email(outlook_item.message_id)
                        elif outlook_item.action == MessageAction.Delete:
                            outlook_api_client.trash_email(outlook_item.message_id)
                        elif outlook_item.action == MessageAction.Reply:
                            recipient_name, recipient_address = split_email_str(outlook_item.sender)
                            outlook_api_client.reply_email_text(outlook_item.message_id, recipient_name,
                                                                recipient_address, outlook_item.reply_message)
                        # elif outlook_item.action == MessageAction.Ignore
                        #     # Ignore
                        #     pass

                        outlook_item.action_result = MessageActionResult.Success
                        log_to_add = action_log_model.ActionLog(
                            at=int(datetime.now().timestamp()),
                            id=outlook_item.id,
                            message=f"{outlook_item.action} {outlook_item.sender} succeed",
                        ).to_dict()
                    except Exception as e:
                        logger.error(e)
                        outlook_item.action_result = MessageActionResult.Error
                        log_to_add = action_log_model.ActionLog(
                            at=int(datetime.now().timestamp()),
                            id=outlook_item.id,
                            message=f"{outlook_item.action} {outlook_item.sender} failed",
                        ).to_dict()
                    finally:
                        with get_session(write=True) as session:
                            # insert action log
                            ReportBatchAction.append_logs(session, the_message.run_id, [
                                log_to_add,
                            ])
                            if outlook_item.action_result == MessageActionResult.Success:
                                ReportBatchAction.increase_success_actions(session, the_message.report_id)
                            else:
                                ReportBatchAction.increase_failed_actions(session, the_message.report_id)
                            # update content
                            Report.update_content_subfield(session, the_message.report_id, "content",
                                                           report_obj.content.to_dict())

    # set batch run status
    with get_session(write=True) as session:
        ReportBatchAction.update(session, the_message.run_id, status=BatchActionRunStatus.Done)


def generate_previous_report(the_message: PreviousReportGenerateMessage):
    """
    Process old email messages from SQS and generate reports.
    Similar to handle_report_update but for historical emails.
    """
    with get_session(write=True) as session:
        Report.update(session, the_message.report_id, content=initialize_report(messages_in_queue={}).to_dict())

    for task_by_account in the_message.task_info:  # handle gmail messages
        # get user account info from db
        with get_session(write=False) as session:
            account = Account.get_by_id(session, task_by_account.account_id)

        # TODO: we add calculate all the message in queue first
        if account.provider == AccountProvider.Google:
            gmail_api_client = GmailAPIClient(account.access_token, account.refresh_token, account.expires_at)
            raw_emails = gmail_api_client.list_emails(max_results=task_by_account.number_of_email)

            with get_session(write=True) as session:
                Report.update_content_subfield(session, the_message.report_id, ReportFieldName.MessagesInQueue,
                                               {EmailSource.Gmail: len(raw_emails)})
            # generate report for historical emails
            report_update_ctrl.update_report_with_gmail_message(
                the_message.user_id,
                str(task_by_account.account_id),
                account.email,
                the_message.report_id,
                raw_emails,
                len(raw_emails),
            )
        else:
            outlook_api_client = OutlookAPIClient(account.access_token, account.refresh_token, account.expires_at)
            raw_emails = outlook_api_client.list_emails(max_results=task_by_account.number_of_email)
            with get_session(write=True) as session:
                Report.update_content_subfield(session, the_message.report_id, ReportFieldName.MessagesInQueue,
                                               {EmailSource.Outlook: len(raw_emails)})
            # generate report for historical emails
            report_update_ctrl.update_report_with_outlook_emails(
                the_message.user_id,
                str(task_by_account.account_id),
                account.email,
                the_message.report_id,
                raw_emails,
                len(raw_emails),
            )

    with get_session(write=True) as session:
        Report.update(session, the_message.report_id, status=ReportStatus.Finalized)


def init():
    init_db()
    init_sqs()


if __name__ == '__main__':
    logger.info('Agent service starting up...')
    init()
    logger.info('Agent service start consuming')
    while True:
        try:
            response = get_sqs_client().receive_message(
                QueueUrl=RuntimeEnv.Instance().SQS_REPORT_ASYNC_ACTION_QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=10,  # long pooling
                AttributeNames=['ApproximateReceiveCount']
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
                    elif sqs_message_obj.action_type == sqs_message_model.ActionType.PREVIOUS_REPORT_GENERATE:
                        generate_previous_report(sqs_message_obj.previous_report_generate_message)
                    elif sqs_message_obj.action_type == sqs_message_model.ActionType.REPORT_BATCH_ACTION:
                        handle_report_batch_action(sqs_message_obj.report_batch_action_message)
                    else:
                        logger.error(f"Unknown action type: {sqs_message_obj.action_type}")
                except Exception as e:
                    file_name, line_number, func_name, text = track_haper_error(e)
                    logger.error(f"Error in {file_name}, line {line_number}, in {func_name}: {text}")
                    logger.error(f"Error processing message: {message['MessageId']}, error: {e}")

                    get_sqs_client().change_message_visibility(
                        QueueUrl=RuntimeEnv.Instance().SQS_REPORT_ASYNC_ACTION_QUEUE_URL,
                        ReceiptHandle=message['ReceiptHandle'],
                        VisibilityTimeout=0  # make it visible again
                    )

                    continue

                # ACK message
                get_sqs_client().delete_message(
                    QueueUrl=RuntimeEnv.Instance().SQS_REPORT_ASYNC_ACTION_QUEUE_URL,
                    ReceiptHandle=message['ReceiptHandle']
                )
                logger.info(f"Successfully ACK message: {message['MessageId']}")
        except Exception as e:
            logger.error(f"Unexpected error occurred: {e}")
