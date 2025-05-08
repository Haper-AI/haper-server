from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from sqlalchemy.orm import make_transient

from app.jobs.refresh_email_sync import init_job, job_main
from biz.controller.gmail_util import GmailAPIClient
from biz.controller.outlook_util import OutlookAPIClient
from biz.dal.message_tracking import MessageTrackingRecord, MessageTrackingStatusExtraInfoKeys
from biz.dal.report import Report
from biz.dal.user import User, Account, AccountProvider
from biz.service.db import get_session
from tests import generate_random_gmail, generate_random_string


@pytest.fixture(scope="module")
def patch_gmail_api():
    # config gmail client api mock
    mock_gmail_client = MagicMock()
    mock_gmail_client.users().watch.return_value.execute.return_value = {
        'historyId': '123',
        'expiration': (datetime.now(timezone.utc) + timedelta(days=7)).timestamp() * 1000,
    }

    mock_credential = MagicMock()
    mock_credential.token = generate_random_string(10)
    mock_credential.expiry = datetime.now() + timedelta(hours=2)
    with patch.object(GmailAPIClient, "client", create=True, new_callable=PropertyMock) as p1:
        with patch.object(GmailAPIClient, "credential", create=True, new_callable=PropertyMock) as p2:
            p1.return_value = mock_gmail_client
            p2.return_value = mock_credential
            yield p1, p2


@pytest.fixture(scope="module")
def patch_outlook_api():
    mock_outlook_client = MagicMock()

    async def patch_sub(*args):
        return None

    mock_outlook_client.subscriptions.by_subscription_id.return_value.patch = patch_sub

    mock_credential = MagicMock()
    mock_credential.access_token = generate_random_string(10)
    mock_credential.refresh_token = generate_random_string(10)
    mock_credential.expires_at = int((datetime.now() + timedelta(hours=2)).timestamp())

    with patch.object(OutlookAPIClient, "client", create=True, new_callable=PropertyMock) as p1:
        with patch.object(OutlookAPIClient, "credential", create=True, new_callable=PropertyMock) as p2:
            p1.return_value = mock_outlook_client
            p2.return_value = mock_credential
            yield p1, p2


@pytest.mark.usefixtures("patch_outlook_api", "patch_gmail_api")
def test_refresh_email_sync_success():
    # Test the successful refresh of email sync
    with get_session(write=True) as session:
        user = User.add(session, "user name", generate_random_gmail(8), email_verified=True)
        account_1 = Account.add(
            session, user.id, AccountProvider.Google, generate_random_string(16),
            "access_token", "refresh_token",
            expires_at=int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            email=user.email
        )
        account_2 = Account.add(
            session, user.id, AccountProvider.Microsoft, generate_random_string(16),
            "access_token", "refresh_token",
            expires_at=int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            email=user.email
        )

        MessageTrackingRecord.add(session, user.id, account_1.id, AccountProvider.Google, extra_info={
            MessageTrackingStatusExtraInfoKeys.Expiration: int(
                (datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()),
            MessageTrackingStatusExtraInfoKeys.PreHistoryID: "123",
        })

        MessageTrackingRecord.add(session, user.id, account_2.id, AccountProvider.Microsoft, extra_info={
            MessageTrackingStatusExtraInfoKeys.Expiration: int(
                (datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()),
            MessageTrackingStatusExtraInfoKeys.SubscriptionID: "subscription_id_123",
        })
        make_transient(user), make_transient(account_1), make_transient(account_2)


    init_job()
    job_main()

    with get_session(write=False) as session:
        # Check if the records are updated
        record_1 = session.query(MessageTrackingRecord).filter_by(
            user_id=user.id,
            account_id=account_1.id,
        ).first()
        assert record_1 is not None
        assert record_1.extra_info[MessageTrackingStatusExtraInfoKeys.Expiration] > int(
            (datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp())

        record_2 = session.query(MessageTrackingRecord).filter_by(
            user_id=user.id,
            account_id=account_2.id,
        ).first()
        assert record_2 is not None
        assert record_2.extra_info[MessageTrackingStatusExtraInfoKeys.Expiration] > int(
            (datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp())