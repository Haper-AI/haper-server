from datetime import datetime, timedelta
from typing import List, Dict

from biz.controller.gmail_util import GmailAPIClient
from biz.controller.outlook_util import OutlookAPIClient
from biz.dal.email import EmailSource
from biz.dal.user import AccountProvider
from biz.dal.message_tracking import MessageTrackingRecord, MessageTrackingStatus
from biz.dal.report import Report
from biz.dal.user import Account
from biz.model import ReportMessagesInQueueFieldName
from biz.service.db import get_session
from biz.service.aws.sqs import send_report_update_message
from biz.model.report import report_update_message as rum_model
from biz.utils.logger import logger
from biz.model.report import report as report_model


def sync_user_gmail_message(email: str, history_id: int):
    with get_session(write=False) as session:
        account = Account.get_by_mail_and_provider(session, email, AccountProvider.Google)
        if account is None:
            # raise ResponseCode.InvalidParam.create_error("email is not connected to a registered account")
            logger.warning("email is not connected to a registered account")
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
        # call watch if necessary, TODO: move to a cronjob
        new_extra_info = tracking_status.extra_info
        if datetime.now() + timedelta(days=1) > datetime.fromtimestamp(tracking_status.extra_info["expiration"]):
            _, expiration = gmail_api_client.watch_gmail()
            new_extra_info["expiration"] = expiration

        # update extra_info
        new_extra_info["pre_history_id"] = history_id
        MessageTrackingRecord.update(session, tracking_status.user_id, tracking_status.account_id,
                                     extra_info=new_extra_info)
        if new_gmail_message:  # update report and send sqs message
            latest_report = Report.get_latest_by_user_id(session, account.user_id, for_update=True)
            if latest_report is None:  # if there is no ongoing report sequence
                logger.warning("no ongoing report sequence for user %s", str(account.user_id))
                return
            if not latest_report.content:
                messages_in_queue = {EmailSource.Gmail: 0}
                Report.update(session, latest_report.id, content=report_model.Report(
                    messages_in_queue=messages_in_queue,
                    summary=[],
                    content=report_model.ReportContent(
                        content_sources=[],
                        gmail=None,
                        outlook=None
                    ),
                ).to_dict())
            else:
                messages_in_queue = latest_report.content[ReportMessagesInQueueFieldName]

            messages_in_queue[EmailSource.Gmail] += len(new_gmail_message)
            logger.info("increasing {} gmail messages, remaining messages in queue: {}".format(len(new_gmail_message),
                                                                                               messages_in_queue))
            # update report content
            Report.update_content_subfield(session, latest_report.id, ReportMessagesInQueueFieldName, messages_in_queue)

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
        with (get_session(write=True) as session):
            account = Account.get_by_mail_and_provider(session, email, AccountProvider.Microsoft)
            if account is None:
                logger.warning("email {} is not connected to a registered account".format(email))
                continue

            tracking_status = MessageTrackingRecord.get_by_user_id_and_account_id(session, account.user_id, account.id)
            if tracking_status is None or tracking_status.status != MessageTrackingStatus.ONGOING:
                logger.warning("message for account {} is not in synchronizing right now".format(account.id))
                continue

            # update subscription if necessary, TODO: move to a cronjob
            if datetime.now() + timedelta(days=1) > datetime.fromtimestamp(
                    tracking_status.extra_info["expiration"]):
                outlook_api_client = OutlookAPIClient(account.access_token, account.refresh_token, account.expires_at)
                new_expiration = outlook_api_client.refresh_watch_outlook(tracking_status.extra_info["subscription_id"])

                new_extra_info = tracking_status.extra_info
                new_extra_info["expiration"] = new_expiration
                MessageTrackingRecord.update(session, tracking_status.user_id, tracking_status.account_id,
                                             extra_info=new_extra_info)

                if outlook_api_client.access_token != account.access_token:
                    Account.update(
                        session,
                        account.id,
                        outlook_api_client.access_token,
                        outlook_api_client.refresh_token,
                        outlook_api_client.expires_at,
                    )

            # update report messages_in_queue field
            latest_report = Report.get_latest_by_user_id(session, account.user_id, for_update=True)
            if latest_report is None:
                logger.warning("no ongoing report sequence for user {}".format(account.user_id))
                continue

            if not latest_report.content:
                messages_in_queue = {EmailSource.Outlook: 0}
                Report.update(session, latest_report.id, content=report_model.Report(
                    messages_in_queue=messages_in_queue,
                    summary=[],
                    content=report_model.ReportContent(
                        content_sources=[],
                        gmail=None,
                        outlook=None
                    ),
                ).to_dict())
            else:
                messages_in_queue = latest_report.content[ReportMessagesInQueueFieldName]

            messages_in_queue[EmailSource.Outlook] += len(message_ids)
            logger.info("increasing {} outlook messages, remaining messages in queue: {}".format(len(message_ids),
                                                                                                 messages_in_queue))

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
            # update report content
            Report.update_content_subfield(session, latest_report.id, ReportMessagesInQueueFieldName, messages_in_queue)
