import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Union

from kiota_abstractions.api_error import APIError
from sqlalchemy.orm import make_transient

from biz.controller.gmail_util import GmailAPIClient
from biz.controller.outlook_util import OutlookAPIClient
from biz.controller.report import start_new_reporting_sequence, end_reporting_sequence
from biz.dal.user import AccountProvider
from biz.dal.message_tracking import MessageTrackingRecord, MessageTrackingStatus, MessageTrackingStatusExtraInfoKeys
from biz.dal.user import Account
from biz.service.db import get_session
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


def start_message_tracking_with_existing_account(user_id: str, account_id: Union[uuid.UUID, str]):
    with get_session(write=True) as session:
        account = Account.get_by_id(session, account_id)
        if not account or str(account.user_id) != user_id:
            raise ResponseCode.InvalidParam.create_error("invalid account id info")

        tracking_record = MessageTrackingRecord.get_by_user_id_and_account_id(session, user_id, account_id)
        if tracking_record and tracking_record.status == MessageTrackingStatus.ONGOING:
            raise ResponseCode.InvalidParam.create_error("message tracking already started for this account")

        if not tracking_record:
            # insert tracking record to db if not exist
            tracking_record = MessageTrackingRecord.add(session, user_id, account_id, account.provider)
        else:
            MessageTrackingRecord.update(session, tracking_record.user_id, tracking_record.account_id,
                                         status=MessageTrackingStatus.ONGOING)

        # if the ongoing message tracking count goes from 0 to 1, start report sequence
        if MessageTrackingRecord.count_ongoing_by_user_id(session, user_id) == 1:
            start_new_reporting_sequence(session, user_id)

        # start sync message with provider
        extra_info = {}
        if account.provider == AccountProvider.Google:
            gmail_api_client = GmailAPIClient(account.access_token, account.refresh_token, account.expires_at)
            history_id, expiration = gmail_api_client.watch_gmail()
            extra_info[MessageTrackingStatusExtraInfoKeys.PreHistoryID] = history_id
            extra_info[MessageTrackingStatusExtraInfoKeys.Expiration] = expiration
            if gmail_api_client.access_token != account.access_token:
                Account.update(
                    session,
                    account.id,
                    gmail_api_client.access_token,
                    expires_at=gmail_api_client.expires_at,
                )
        elif account.provider == AccountProvider.Microsoft:
            outlook_api_client = OutlookAPIClient(account.access_token, account.refresh_token, account.expires_at)
            subscription_id, expiration = outlook_api_client.watch_outlook()
            extra_info[MessageTrackingStatusExtraInfoKeys.Expiration] = expiration
            extra_info[MessageTrackingStatusExtraInfoKeys.SubscriptionID] = subscription_id

            if outlook_api_client.access_token != account.access_token:
                Account.update(
                    session,
                    account.id,
                    outlook_api_client.access_token,
                    refresh_token=outlook_api_client.refresh_token,
                    expires_at=outlook_api_client.expires_at,
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

        extra_info = {}
        # start sync message with provider
        if provider == AccountProvider.Google:
            gmail_api_client = GmailAPIClient(account.access_token, account.refresh_token, account.expires_at)
            history_id, expiration = gmail_api_client.watch_gmail()
            extra_info[MessageTrackingStatusExtraInfoKeys.Expiration] = expiration
            extra_info[MessageTrackingStatusExtraInfoKeys.PreHistoryID] = history_id
        elif provider == AccountProvider.Microsoft:
            outlook_api_client = OutlookAPIClient(account.access_token, account.refresh_token, account.expires_at)
            subscription_id, expiration = outlook_api_client.watch_outlook()
            extra_info[MessageTrackingStatusExtraInfoKeys.Expiration] = expiration
            extra_info[MessageTrackingStatusExtraInfoKeys.SubscriptionID] = subscription_id

        # create tracking record
        tracking_record = MessageTrackingRecord.add(session, user_id, account.id, account.provider,
                                                    extra_info=extra_info)

        # if the ongoing message tracking count goes from 0 to 1, start report sequence
        if MessageTrackingRecord.count_ongoing_by_user_id(session, user_id) == 1:
            start_new_reporting_sequence(session, user_id)

        make_transient(tracking_record), make_transient(account)

    return {
        "account_id": account.id,
        "email": account.email,
        "provider": account.provider,
        "status": tracking_record.status,
        "created_at": tracking_record.created_at,
        "updated_at": tracking_record.updated_at,
    }


def stop_message_tracking(user_id: str, account_id: Union[uuid.UUID, str]):
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
            gmail_api_client = GmailAPIClient(account.access_token, account.refresh_token, account.expires_at)
            gmail_api_client.stop_watch()

            if gmail_api_client.access_token != account.access_token:
                Account.update(
                    session,
                    account.id,
                    gmail_api_client.access_token,
                    expires_at=gmail_api_client.expires_at,
                )
        elif account.provider == AccountProvider.Microsoft:
            outlook_api_client = OutlookAPIClient(account.access_token, account.refresh_token, account.expires_at)
            try:
                outlook_api_client.stop_watch_outlook(tracking_record.extra_info["subscription_id"])
            except APIError as e:
                if e.response_status_code == 404:
                    logging.info("watch already expired")
                else:
                    raise e

            if outlook_api_client.access_token != account.access_token:
                Account.update(
                    session,
                    account.id,
                    outlook_api_client.access_token,
                    refresh_token=outlook_api_client.refresh_token,
                    expires_at=outlook_api_client.expires_at,
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
