import asyncio
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional

from msgraph.generated.models.subscription import Subscription
from sqlalchemy.orm import make_transient

from biz.controller.report import start_new_reporting_sequence, end_reporting_sequence
from biz.dal.user import AccountProvider
from biz.dal.message_tracking import MessageTrackingRecord, MessageTrackingStatus
from biz.dal.user import Account
from biz.service.aws.sm import get_outlook_sub_public_b64
from biz.service.db import get_session
from biz.utils.env import RuntimeEnv
from biz.utils.gmail import build_gmail_client
from biz.utils.microsoft import build_microsoft_graph_client
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
                        'email': account.email,
                        'provider': account.provider,
                        'status': MessageTrackingStatus.NOT_STARTED,
                    })
                else:
                    result.append({
                        'account_id': account.id,
                        'email': account.email,
                        'provider': account.provider,
                        'status': message_tracking_status_by_account[account.id].status,
                        'created_at': message_tracking_status_by_account[account.id].created_at,
                        'updated_at': message_tracking_status_by_account[account.id].updated_at,
                    })

    return result


def watch_gmail(access_token: str, refresh_token: str, expires_at: int):
    gmail_api_client, credential = build_gmail_client(
        access_token,
        refresh_token,
        expires_at
    )
    gmail_watch_resp = gmail_api_client.users().watch(
        userId='me',
        body={
            'topicName': RuntimeEnv.Instance().GMAIL_WATCH_PUB_SUB_TOPIC,
            'labelIds': ['INBOX'],
            'labelFilterBehavior': 'INCLUDE'
        }
    ).execute()
    history_id = gmail_watch_resp.get('historyId')
    expiration = gmail_watch_resp.get('expiration')
    return history_id, expiration, credential


def watch_outlook(access_token: str, refresh_token: str, expires_at: int):
    # see more from: https://learn.microsoft.com/en-us/graph/api/subscription-post-subscriptions?view=graph-rest-1.0&tabs=python#tabpanel_1_python
    msgraph_api_client, credential = build_microsoft_graph_client(
        access_token,
        refresh_token,
        expires_at
    )
    watch_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10070)
    request_body = Subscription(
        change_type="created",
        notification_url=RuntimeEnv.Instance().OUTLOOK_SYNC_WEBHOOK_URL,
        # for Outlook mail resource: see more from: https://learn.microsoft.com/en-us/graph/api/resources/change-notifications-api-overview?view=graph-rest-1.0
        resource="me/mailFolders('Inbox')/messages?$select=toRecipients",
        # for expiration, see more from: https://learn.microsoft.com/en-us/graph/api/resources/subscription?view=graph-rest-1.0#subscription-lifetime
        expiration_date_time=watch_expires_at,
        latest_supported_tls_version="v1_2",
        include_resource_data=True,
        encryption_certificate_id=RuntimeEnv.Instance().MICROSOFT_CERTIFICATE_KEY_ID,
        encryption_certificate=get_outlook_sub_public_b64(),
    )
    subscribe = asyncio.run(msgraph_api_client.subscriptions.post(request_body))
    subscription_id = subscribe.id
    return subscription_id, int(watch_expires_at.timestamp()), credential


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
        else:
            MessageTrackingRecord.update(session, tracking_record.user_id, tracking_record.account_id,
                                         status=MessageTrackingStatus.ONGOING)

        # if the ongoing message tracking count goes from 0 to 1, start report sequence
        if MessageTrackingRecord.count_ongoing_by_user_id(session, user_id) == 1:
            start_new_reporting_sequence(session, user_id)

        # start sync message with provider
        extra_info = {}
        if account.provider == AccountProvider.Google:
            history_id, expiration, credential = watch_gmail(
                account.access_token,
                account.refresh_token,
                account.expires_at
            )
            extra_info['pre_history_id'] = history_id
            extra_info['expiration'] = expiration
            if credential.token != account.access_token:
                Account.update(
                    session,
                    account.id,
                    credential.token,
                    expires_at=int(credential.expiry.timestamp()),
                )
        elif account.provider == AccountProvider.Microsoft:
            subscription_id, expiration, credential = watch_outlook(
                account.access_token,
                account.refresh_token,
                account.expires_at
            )
            extra_info['expiration'] = expiration
            extra_info['subscription_id'] = subscription_id

            if credential.access_token != account.access_token:
                Account.update(
                    session,
                    account.id,
                    credential.access_token,
                    refresh_token=credential.refresh_token,
                    expires_at=credential.expiry,
                )

        MessageTrackingRecord.update(
            session, user_id, account.id,
            status=MessageTrackingStatus.ONGOING,
            extra_info=extra_info
        )

        tracking_record.status = MessageTrackingStatus.ONGOING
        tracking_record.updated_at = datetime.now(timezone.utc)

        make_transient(tracking_record), make_transient(account)

    return {
        "account_id": account.id,
        "email": account.email,
        "provider": account.provider,
        "status": tracking_record.status,
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

        # if the ongoing message tracking count goes from 0 to 1, start report sequence
        if MessageTrackingRecord.count_ongoing_by_user_id(session, user_id) == 1:
            start_new_reporting_sequence(session, user_id)

        extra_info = {}
        # start sync message with provider
        if provider == AccountProvider.Google:
            history_id, expiration, credential = watch_gmail(
                account.access_token,
                account.refresh_token,
                account.expires_at
            )
            extra_info['expiration'] = expiration
            extra_info['pre_history_id'] = history_id
        elif provider == AccountProvider.Microsoft:
            subscription_id, expiration, credential = watch_outlook(
                account.access_token,
                account.refresh_token,
                account.expires_at
            )
            extra_info['expiration'] = expiration
            extra_info['subscription_id'] = subscription_id

        # create tracking record
        tracking_record = MessageTrackingRecord.add(session, user_id, account.id, extra_info=extra_info)

        make_transient(tracking_record), make_transient(account)

    return {
        "account_id": account.id,
        "email": account.email,
        "provider": account.provider,
        "status": tracking_record.status,
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

        # if the ongoing message tracking count goes from 1 to 0, end report sequence
        if MessageTrackingRecord.count_ongoing_by_user_id(session, user_id) == 0:
            end_reporting_sequence(session, user_id)

        # stop message sync with provider
        if account.provider == AccountProvider.Google:
            gmail_api_client, credential = build_gmail_client(
                account.access_token,
                account.refresh_token,
                account.expires_at
            )

            gmail_api_client.users().stop(userId='me').execute()

            if credential.token != account.access_token:
                Account.update(
                    session,
                    account.id,
                    credential.token,
                    expires_at=int(credential.expiry.timestamp())
                )
        elif account.provider == AccountProvider.Microsoft:
            msgraph_api_client, credential = build_microsoft_graph_client(
                account.access_token,
                account.refresh_token,
                account.expires_at
            )
            asyncio.run(msgraph_api_client.subscriptions.by_subscription_id(
                tracking_record.extra_info["subscription_id"]).delete())

            if credential.access_token != account.access_token:
                Account.update(
                    session,
                    account.id,
                    credential.access_token,
                    refresh_token=credential.refresh_token,
                    expires_at=credential.expiry,
                )

        make_transient(tracking_record), make_transient(account)

    return {
        "account_id": account.id,
        "email": account.email,
        "provider": account.provider,
        "status": tracking_record.status,
        "created_at": tracking_record.created_at,
        "updated_at": tracking_record.updated_at,
    }
