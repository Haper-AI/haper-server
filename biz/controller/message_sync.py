from datetime import datetime
from typing import List, Dict

from biz.controller.gmail_util import GmailAPIClient
from biz.dal.email import EmailSource
from biz.dal.user import AccountProvider
from biz.dal.message_tracking import MessageTrackingRecord, MessageTrackingStatus, MessageTrackingStatusExtraInfoKeys
from biz.dal.report import Report, ReportStatus
from biz.dal.user import Account
from biz.dal.user_setting import UserSetting, DEFAULT_REPORT_MAX_TIME_DURATION
from biz.model import ReportFieldName
from biz.service.db import get_session
from biz.service.aws.sqs import send_report_update_message
from biz.model.report import report_update_message as rum_model
from biz.utils.logger import logger
from biz.model.report import report as report_model


# TODO: to avoid duplicate message process, use redis to cache processed message ids

def initialize_report(messages_in_queue=None):
    if messages_in_queue is None:
        messages_in_queue = {}
    return report_model.Report(
        messages_in_queue=messages_in_queue,
        summary=[],
        content=report_model.ReportContent(
            content_sources=[],
            gmail=None,
            outlook=None
        ),
    )


def sync_user_gmail_message(email: str, history_id: int):
    with get_session(write=False) as session:
        account = Account.get_by_mail_and_provider(session, email, AccountProvider.Google)
        if account is None:
            # raise ResponseCode.InvalidParam.create_error("email is not connected to a registered account")
            logger.warning("email {} is not connected to a registered account".format(email))
            return

        tracking_status = MessageTrackingRecord.get_by_user_id_and_account_id(session, account.user_id, account.id)
        if tracking_status is None or tracking_status.status != MessageTrackingStatus.ONGOING:
            logger.warning("message for account {} is not in synchronizing right now".format(account.id))
            return

    # get messages added
    gmail_api_client = GmailAPIClient(account.access_token, account.refresh_token, account.expires_at)
    new_gmail_message = gmail_api_client.list_new_mails(tracking_status.extra_info["pre_history_id"], history_id)

    with get_session(write=True) as session:
        # update the access_token if necessary
        if gmail_api_client.access_token != account.access_token:
            Account.update(
                session,
                account.id,
                gmail_api_client.access_token,
                expires_at=gmail_api_client.expires_at,
            )

        # update extra_info
        MessageTrackingRecord.update_extra_info_subfield(
            session, tracking_status.user_id, tracking_status.account_id,
            MessageTrackingStatusExtraInfoKeys.PreHistoryID,
            history_id
        )

        # update report and send sqs message if new messages are found
        if new_gmail_message:
            latest_report = Report.get_latest_by_user_id(session, account.user_id, for_update=True)
            if latest_report is None:  # if there is no ongoing report sequence
                logger.warning("no ongoing report sequence for user %s", str(account.user_id))
                return
            if not latest_report.content:
                messages_in_queue = {EmailSource.Gmail: 0}
                Report.update(session, latest_report.id, content=initialize_report(messages_in_queue).to_dict())
            else:
                messages_in_queue = latest_report.content[ReportFieldName.MessagesInQueue]

            messages_in_queue[EmailSource.Gmail] += len(new_gmail_message)
            # update report content
            Report.update_content_subfield(session, latest_report.id, ReportFieldName.MessagesInQueue,
                                           messages_in_queue)
            logger.info("increasing {} gmail messages, remaining messages in queue: {}".format(
                len(new_gmail_message),
                messages_in_queue
            ))

            # send the new messages to sqs for the report consumer
            report_update_message = rum_model.ReportUpdateMessage(
                user_id=str(account.user_id),
                report_id=str(latest_report.id),
                messages=rum_model.Messages(
                    gmail=rum_model.Gmail(
                        account_id=str(account.id),
                        new_messages=new_gmail_message,
                    ),
                    outlook=None
                ),
            )
            send_report_update_message(report_update_message, str(latest_report.id))
            logger.info("send sqs report update message")

    return


def sync_user_outlook_message(message_ids_by_email: Dict[str, List[str]]):
    for email, message_ids in message_ids_by_email.items():
        with get_session(write=True) as session:
            account = Account.get_by_mail_and_provider(session, email, AccountProvider.Microsoft)
            if account is None:
                logger.warning("email {} is not connected to a registered account".format(email))
                continue

            tracking_status = MessageTrackingRecord.get_by_user_id_and_account_id(session, account.user_id, account.id)
            if tracking_status is None or tracking_status.status != MessageTrackingStatus.ONGOING:
                logger.warning("message for account {} is not in synchronizing right now".format(account.id))
                continue

            # update report messages_in_queue field
            latest_report = Report.get_latest_by_user_id(session, account.user_id, for_update=True)
            if latest_report is None:
                logger.warning("no ongoing report sequence for user {}".format(account.user_id))
                continue

            if not latest_report.content:
                messages_in_queue = {EmailSource.Outlook: 0}
                Report.update(session, latest_report.id, content=initialize_report(messages_in_queue).to_dict())
            else:
                messages_in_queue = latest_report.content[ReportFieldName.MessagesInQueue]

            messages_in_queue[EmailSource.Outlook] += len(message_ids)

            # update report content
            Report.update_content_subfield(session, latest_report.id, ReportFieldName.MessagesInQueue,
                                           messages_in_queue)
            logger.info("increasing {} outlook messages, remaining messages in queue: {}".format(
                len(message_ids),
                messages_in_queue
            ))

            # send the new messages to sqs for the report consumer
            report_update_message = rum_model.ReportUpdateMessage(
                user_id=str(account.user_id),
                report_id=str(latest_report.id),
                messages=rum_model.Messages(
                    gmail=None,
                    outlook=rum_model.Outlook(
                        account_id=str(account.id),
                        new_messages=message_ids,
                    )
                ),
            )
            send_report_update_message(report_update_message, str(latest_report.id))
            logger.info("send sqs report update message")
