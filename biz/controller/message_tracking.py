from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import make_transient

from biz.dal.message_tracking import MessageTrackingRecord, MessageTrackingStatus
from biz.dal.user import Account
from biz.service.db import get_session
from biz.utils.env import RuntimeEnv
from biz.utils.gmail import build_gmail_client
from biz.utils.response import ResponseCode


def list_user_message_tracking_status(user_id: str):
    result = []
    with get_session(write=False) as session:
        user_accounts = Account.list_by_user_id(session, user_id)
        if user_accounts:
            user_message_tracking_status = MessageTrackingRecord.list_by_user_id(session, user_id)
            message_tracking_status_by_account = {}
            for tracking_status in user_message_tracking_status:
                message_tracking_status_by_account[tracking_status.account_id] = tracking_status
            for account in user_accounts:
                if account.id not in message_tracking_status_by_account:
                    result.append({
                        'account_id': account.id,
                        'provider': account.provider,
                        'tracking_status': MessageTrackingStatus.NOT_STARTED,
                    })
                else:
                    result.append({
                        'account_id': account.id,
                        'provider': account.provider,
                        'tracking_status': message_tracking_status_by_account[account.id].status,
                        'created_at': message_tracking_status_by_account[account.id].created_at,
                        'updated_at': message_tracking_status_by_account[account.id].updated_at,
                    })

    return result


def start_message_tracking_with_existing_account(user_id: str, account_id: str):
    with get_session(write=True) as session:
        account = Account.get_by_id(session, account_id)
        if not account or str(account.user_id) != user_id:
            raise ResponseCode.InvalidParam.create_error("invalid account id info")

        tracking_record = MessageTrackingRecord.get_by_user_id_and_account_id(session, user_id, account_id)
        if tracking_record and tracking_record.status == MessageTrackingStatus.ONGOING:
            raise ResponseCode.InvalidParam.create_error("message tracking already started for this account")

        if not tracking_record:
            # insert tracking record to db if not exist
            tracking_record = MessageTrackingRecord.add(session, user_id, account_id)

        # start sync message with provider
        if account.provider == 'google':
            gmail_api_client, credential = build_gmail_client(
                account.access_token,
                account.refresh_token,
                datetime.fromtimestamp(account.expires_at)
            )
            gmail_watch_resp = gmail_api_client.users().watch(
                userId='me',
                body={
                    'topicName': RuntimeEnv.Instance().GMAIL_WATCH_PUB_SUB_TOPIC,
                    'labelIds': ['INBOX'],
                    'labelFilterBehavior': 'INCLUDE'
                }
            ).execute()

            # history_id = gmail_watch_resp.get('historyId')
            expiration = gmail_watch_resp.get('expiration')

            MessageTrackingRecord.update(
                session, user_id, account.id,
                status=MessageTrackingStatus.ONGOING,
                extra_info={'expiration': expiration}
            )
            tracking_record.status = MessageTrackingStatus.ONGOING
            tracking_record.updated_at = datetime.now(timezone.utc)

            if credential.token != account.access_token:
                Account.update_tokens(
                    session,
                    account.id,
                    credential.token,
                    expires_at=int(credential.expiry.timestamp()),
                )

        make_transient(tracking_record), make_transient(account)

    return {
        "account_id": account.id,
        "provider": account.provider,
        "tracking_status": tracking_record.status,
        "created_at": tracking_record.created_at,
        "updated_at": tracking_record.updated_at,
    }


def start_message_tracking_with_new_account(user_id: str, provider: str, provider_account_id: str,
                                            access_token: str, refresh_token: Optional[str] = None,
                                            expires_at: Optional[int] = None,
                                            email: Optional[str] = None):
    with get_session(write=True) as session:
        account = Account.get_by_provider_and_provider_id(session, provider, provider_account_id)
        if account:
            raise ResponseCode.InvalidParam.create_error("account already exists")

        # create account
        account = Account.add(session, user_id, provider, provider_account_id,
                              access_token, refresh_token, expires_at, email)

        extra_info = {}
        # start sync message with provider
        if provider == 'google':
            gmail_api_client, credential = build_gmail_client(
                account.access_token,
                account.refresh_token,
                datetime.fromtimestamp(account.expires_at)
            )
            gmail_watch_resp = gmail_api_client.users().watch(
                userId='me',
                topicName=RuntimeEnv.Instance().GMAIL_WATCH_PUB_SUB_TOPIC,
                labelIds=['INBOX'],
                labelFilterBehavior="INCLUDE"
            ).execute()

            # history_id = gmail_watch_resp.get('historyId')
            expiration = gmail_watch_resp.get('expiration')
            extra_info['expiration'] = expiration

        # create tracking record
        tracking_record = MessageTrackingRecord.add(session, user_id, account.id, extra_info=extra_info)

        make_transient(tracking_record), make_transient(account)

    return {
        "account_id": account.id,
        "provider": account.provider,
        "tracking_status": tracking_record.status,
        "created_at": tracking_record.created_at,
        "updated_at": tracking_record.updated_at,
    }


def end_message_tracking(user_id: str, account_id: str):
    with get_session(write=True) as session:
        account = Account.get_by_id(session, account_id)
        if not account or str(account.user_id) != user_id:
            raise ResponseCode.InvalidParam.create_error("invalid account id info")

        tracking_record = MessageTrackingRecord.get_by_user_id_and_account_id(session, user_id, account_id)
        if not tracking_record:
            raise ResponseCode.InvalidParam.create_error("no message tracking configured for this account")

        if tracking_record.status != MessageTrackingStatus.ONGOING:
            raise ResponseCode.InvalidParam.create_error("current message tracking status can not be ended")

        MessageTrackingRecord.update(session, user_id, account.id, status=MessageTrackingStatus.STOPPED)
        tracking_record.status = MessageTrackingStatus.STOPPED
        tracking_record.updated_at = datetime.now(timezone.utc)

        # stop message sync with provider
        if account.provider == 'google':
            gmail_api_client, credential = build_gmail_client(
                account.access_token,
                account.refresh_token,
                datetime.fromtimestamp(account.expires_at)
            )

            gmail_api_client.users().stop(userId='me').execute()

            if credential.token != account.access_token:
                Account.update_tokens(
                    session,
                    account.id,
                    credential.token,
                    expires_at=int(credential.expiry.timestamp())
                )

        make_transient(tracking_record), make_transient(account)

    return {
        "account_id": account.id,
        "provider": account.provider,
        "tracking_status": tracking_record.status,
        "created_at": tracking_record.created_at,
        "updated_at": tracking_record.updated_at,
    }
