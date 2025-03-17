import json
from datetime import datetime
from typing import List

from biz.dal.report import Report
from biz.dal.user import Account
from biz.service.db import get_session
from biz.service.sqs import send_report_update_message
from biz.model.report import report_update_message as rum_model
from biz.utils.gmail import build_gmail_client
from biz.utils.logger import logger
# from biz.utils.response import ResponseCode
from biz.model.report import report as report_model


def sync_user_gmail_message(email: str, history_id: int):
    with get_session(write=False) as session:
        account = Account.get_by_gmail(session, email)
        if account is None:
            # raise ResponseCode.InvalidParam.create_error("email is not connected to a registered account")
            logger.warning("email is not connected to a registered account")
            return

    # get messages added
    gmail_api_client, credential = build_gmail_client(
        account.access_token,
        account.refresh_token,
        datetime.fromtimestamp(account.expires_at)
    )

    has_next_page = True
    page_token = None
    new_gmail_message: List[rum_model.GmailNewMessage] = []

    while has_next_page:
        response = gmail_api_client.users().history().list(
            userId="me",
            startHistoryId=history_id,
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

    if new_gmail_message:
        with get_session(write=True) as session:
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

            if "gmail" not in messages_in_queue:
                messages_in_queue["gmail"] = len(new_gmail_message)
            else:
                messages_in_queue["gmail"] += len(new_gmail_message)

            # send the new messages to sqs for the report consumer
            report_update_message = rum_model.ReportUpdateMessage(
                user_id=str(account.user_id),
                report_id=str(latest_report.id),
                messages=rum_model.Messages(
                    gmail=rum_model.Gmail(
                        account_info=rum_model.AccountInfo(
                            account_id=str(account.id),
                        ),
                        new_messages=new_gmail_message,
                    ),
                ),
            )
            send_report_update_message(report_update_message, str(latest_report.id))

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
