from typing import List, Dict

from biz.dal.email import EmailSource
from biz.dal.user import AccountProvider
from biz.dal.message_tracking import MessageTrackingRecord, MessageTrackingStatus
from biz.dal.report import Report
from biz.dal.user import Account
from biz.service.db import get_session
from biz.service.aws.sqs import send_report_update_message
from biz.model.report import report_update_message as rum_model
from biz.utils.gmail import build_gmail_client
from biz.utils.logger import logger
# from biz.utils.response import ResponseCode
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
    gmail_api_client, credential = build_gmail_client(
        account.access_token,
        account.refresh_token,
        account.expires_at
    )

    pre_history_id = tracking_status.extra_info["pre_history_id"]
    has_next_page = True
    page_token = None
    new_gmail_message: List[rum_model.GmailNewMessage] = []

    while has_next_page:
        response = gmail_api_client.users().history().list(
            userId="me",
            startHistoryId=pre_history_id,
            pageToken=page_token
        ).execute()

        for history in response.get('history', []):
            if "messagesAdded" in history:
                for message in history['messagesAdded']:
                    new_gmail_message.append(rum_model.GmailNewMessage(
                        message_id=message["message"]["id"],
                        thread_id=message["message"]["threadId"],
                    ))
        page_token = response.get("nextPageToken")
        if not page_token:
            has_next_page = False

    with get_session(write=True) as session:
        # update extra_info
        new_extra_info = tracking_status.extra_info
        new_extra_info["pre_history_id"] = history_id
        MessageTrackingRecord.update(session, tracking_status.user_id, tracking_status.account_id,
                                     extra_info=new_extra_info)
        if new_gmail_message:
            latest_report = Report.get_latest_by_user_id(session, account.user_id, for_update=True)
            if latest_report is None:  # if there is no ongoing report sequence
                logger.warning("no ongoing report sequence for user %s", str(account.user_id))
                return
            if not latest_report.content:
                Report.update(session, latest_report.id, content=report_model.Report(
                    messages_in_queue={
                        "gmail": 0
                    },
                    summary=[],
                    content=report_model.ReportContent(
                        content_sources=[],
                        gmail=None,
                    ),
                ).to_dict())
                messages_in_queue = {}
            else:
                messages_in_queue = latest_report.content["messages_in_queue"]

            if EmailSource.Gmail not in messages_in_queue:
                messages_in_queue[EmailSource.Outlook] = len(new_gmail_message)
            else:
                messages_in_queue[EmailSource.Outlook] += len(new_gmail_message)

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

            # update report content
            Report.update_content_subfield(session, latest_report.id, "messages_in_queue", messages_in_queue)

    # update the access_token if necessary
    if credential.token != account.access_token:
        with get_session(write=True) as session:
            Account.update(
                session,
                account.id,
                credential.token,
                expires_at=int(credential.expiry.timestamp()),
            )

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
                Report.update(session, latest_report.id, content=report_model.Report(
                    messages_in_queue={
                        "outlook": 0
                    },
                    summary=[],
                    content=report_model.ReportContent(
                        content_sources=[],
                        gmail=None,
                    ),
                ).to_dict())
                messages_in_queue = {}
            else:
                messages_in_queue = latest_report.content["messages_in_queue"]

            if EmailSource.Outlook not in messages_in_queue:
                messages_in_queue[EmailSource.Outlook] = len(message_ids)
            else:
                messages_in_queue[EmailSource.Outlook] += len(message_ids)

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
            Report.update_content_subfield(session, latest_report.id, "messages_in_queue", messages_in_queue)