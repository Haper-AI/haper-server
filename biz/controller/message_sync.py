import json
from datetime import datetime, timezone

from biz.dal.user import Account
from biz.service.db import get_session
from biz.service.sqs import send_report_update_message
from biz.utils.gmail import build_gmail_client
from biz.utils.logger import logger
from biz.utils.response import ResponseCode


def sync_user_gmail_message(email: str, history_id: int):
    with get_session(write=False) as session:
        account_info = Account.get_by_gmail(session, email)
        if account_info is None:
            # raise ResponseCode.InvalidParam.create_error("email is not connected to a registered account")
            logger.warning("email is not connected to a registered account")
            return

    # get messages added
    gmail_api_client, credential = build_gmail_client(
        account_info.access_token,
        account_info.refresh_token,
        datetime.fromtimestamp(account_info.expires_at)
    )

    has_next_page = True
    page_token = None
    new_gmail_message = []

    while has_next_page:
        response = gmail_api_client.users().history().list(
            userId="me",
            startHistoryId=history_id,
            pageToken=page_token
        ).execute()

        for history in response.get('history', []):
            if "messagesAdded" in history:
                for message in history['messagesAdded']:
                    new_gmail_message.append({
                        "id": message["message"]["id"],
                        "thread_id": message["message"]["threadId"],
                    })
        page_token = response.get("nextPageToken")
        if not page_token:
            has_next_page = False

    # send the new messages to sqs that connected to haper-agent
    # TODO: update message format
    send_report_update_message(json.dumps({
        "messages": {
            "gmail": {
                "new_messages": new_gmail_message,
            }
        }
    }))

    # update the access_token if necessary
    if credential.token != account_info.access_token:
        with get_session(write=True) as session:
            Account.update_tokens(
                session,
                account_info.provider,
                account_info.provider_account_id,
                credential.token,
                expires_at=int(credential.expiry.timestamp()),
            )

    return
