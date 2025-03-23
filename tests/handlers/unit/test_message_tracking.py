import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest
from msgraph.generated.models.subscription import Subscription
from sqlalchemy.orm import make_transient

from biz.dal.user import AccountProvider
from biz.dal.message_tracking import MessageTrackingRecord, MessageTrackingStatus
from biz.dal.report import Report
from biz.dal.user import Account, User
from biz.handler.middleware import gen_jwt_auth
from biz.service.db import get_session
from biz.utils.env import RuntimeEnv

from tests import generate_random_string, generate_random_gmail, generate_random_outlook_email
from .conftest import client, new_user, new_user_gmail_account, db_add_new_account


@pytest.fixture
def new_user_gmail_tracking_record():
    email = generate_random_gmail(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email, email_verified=True)
        account = db_add_new_account(session, user.id, email, provider=AccountProvider.Google)
        record = MessageTrackingRecord.add(session, str(user.id), str(account.id), extra_info={
            "some_info_key": "some_info_value"
        })
        Report.add(session, user.id, {})

        make_transient(user), make_transient(account), make_transient(record)
    return user, account, record


@pytest.fixture
def new_user_outlook_tracking_record():
    email = generate_random_outlook_email(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email, email_verified=True)
        account = db_add_new_account(session, user.id, email, provider=AccountProvider.Microsoft)
        record = MessageTrackingRecord.add(session, str(user.id), str(account.id), extra_info={
            "subscription_id": str(uuid.uuid4()),
        })
        Report.add(session, user.id, {})

        make_transient(user), make_transient(account), make_transient(record)
    return user, account, record


@pytest.fixture(scope="module")
def patch_gmail_watch_stop():
    # config gmail client api mock
    mock_gmail_client = MagicMock()
    mock_gmail_client.users().watch.return_value.execute.return_value = {
        'historyId': '123',
        'expiration': int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()),
    }
    mock_gmail_client.users().stop.return_value.execute.return_value = {}

    mock_credential = MagicMock()
    mock_credential.token = generate_random_string(10)
    mock_credential.expiry = datetime.now() + timedelta(hours=2)
    with patch('biz.controller.message_tracking.build_gmail_client',
               return_value=(mock_gmail_client, mock_credential)) as mock_build_gmail_account:
        yield mock_build_gmail_account


@pytest.fixture(scope="module")
def patch_outlook_subscription_create_delete():
    mock_outlook_client = MagicMock()

    async def create_sub(*args):
        sub = Subscription(id=str(uuid.uuid4()))
        return sub

    async def delete_sub():
        return None

    mock_outlook_client.subscriptions.post = create_sub
    mock_outlook_client.subscriptions.return_value.by_subscription_id.return_value.delete = delete_sub

    mock_credential = MagicMock()
    mock_credential.access_token = generate_random_string(10)
    mock_credential.refresh_token = generate_random_string(10)
    mock_credential.expiry = int((datetime.now() + timedelta(hours=2)).timestamp())

    with patch('biz.controller.message_tracking.build_microsoft_graph_client',
               return_value=(mock_outlook_client, mock_credential)) as mock_build_microsoft_graph:
        yield mock_build_microsoft_graph


@pytest.fixture(scope="module")
def patch_outlook_sub_public_key():
    with patch('biz.controller.message_tracking.get_outlook_sub_public_b64',
               return_value="public-key") as mock_public_key:
        yield mock_public_key


class TestMessageTrackingGetStatus:
    def test_success(self, client, new_user_gmail_tracking_record):
        user, _, _ = new_user_gmail_tracking_record
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
        response = client.get("/api/v1/message/tracking/status")
        assert response.status_code == 200
        assert len(response.get_json()['data']['tracking_status']) != 0


class TestMessageTrackingStart:
    class TestSuccess:
        @pytest.mark.usefixtures("patch_gmail_watch_stop")
        def test_success_by_exist_google_account(self, client, new_user_gmail_account):
            user, account = new_user_gmail_account
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/message/tracking/start", json={
                "account_id": account.id,
            })

            assert response.status_code == 200
            assert response.get_json()['data']['new_tracking_status']

        @pytest.mark.usefixtures("patch_gmail_watch_stop")
        def test_success_by_new_google_account(self, client, new_user):
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(new_user.id)))
            response = client.post("/api/v1/message/tracking/start", json={
                "account": {
                    "provider": AccountProvider.Google,
                    "provider_account_id": generate_random_string(16),
                    "access_token": "access_token",
                    "refresh_token": "refresh_token",
                    "expires_at": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
                    "email": new_user.email,
                }
            })
            assert response.status_code == 200
            assert response.get_json()['data']['new_tracking_status']

        @pytest.mark.usefixtures("patch_outlook_subscription_create_delete")
        @pytest.mark.usefixtures("patch_outlook_sub_public_key")
        def test_success_by_exist_outlook_account(self, client, new_user_outlook_account):
            user, account = new_user_outlook_account
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/message/tracking/start", json={
                "account_id": account.id,
            })

            assert response.status_code == 200
            assert response.get_json()['data']['new_tracking_status']

        @pytest.mark.usefixtures("patch_outlook_subscription_create_delete")
        @pytest.mark.usefixtures("patch_outlook_sub_public_key")
        def test_success_by_exist_outlook_account(self, client, new_user):
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(new_user.id)))
            response = client.post("/api/v1/message/tracking/start", json={
                "account": {
                    "provider": AccountProvider.Microsoft,
                    "provider_account_id": generate_random_string(16),
                    "access_token": "access_token",
                    "refresh_token": "refresh_token",
                    "expires_at": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
                    "email": new_user.email,
                }
            })
            assert response.status_code == 200
            assert response.get_json()['data']['new_tracking_status']

    class TestFail:
        def test_fail_by_invalid_account_id(self, client, new_user):
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(new_user.id)))
            response = client.post("/api/v1/message/tracking/start", json={
                "account_id": str(uuid.uuid4()),
            })

            assert response.status_code == 400

        def test_fail_by_invalid_status(self, client, new_user_gmail_tracking_record):
            user, _, _ = new_user_gmail_tracking_record
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/message/tracking/start", json={
                "account_id": str(uuid.uuid4()),
            })

            assert response.status_code == 400


class TestMessageTrackingStop:
    class TestSuccess:
        @pytest.mark.usefixtures("patch_gmail_watch_stop")
        def test_success_with_gmail(self, client, new_user_gmail_tracking_record):
            user, account, _ = new_user_gmail_tracking_record
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/message/tracking/stop", json={
                "account_id": account.id,
            })

            assert response.status_code == 200
            assert response.get_json()['data']['new_tracking_status']

        @pytest.mark.usefixtures("patch_outlook_subscription_create_delete")
        def test_success_with_outlook(self, client, new_user_outlook_tracking_record):
            user, account, _ = new_user_outlook_tracking_record
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/message/tracking/stop", json={
                "account_id": account.id,
            })

            assert response.status_code == 200
            assert response.get_json()['data']['new_tracking_status']

    class TestFail:
        def test_fail_by_invalid_account_id(self, client, new_user):
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(new_user.id)))
            response = client.post("/api/v1/message/tracking/stop", json={
                "account_id": str(uuid.uuid4()),
            })

            assert response.status_code == 400

        def test_fail_by_no_tracking_configured(self, client, new_user_gmail_account):
            user, account = new_user_gmail_account
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/message/tracking/stop", json={
                "account_id": account.id,
            })

            assert response.status_code == 400

        def test_fail_by_invalid_tracking_status(self, client, new_user_gmail_tracking_record):
            user, account, record = new_user_gmail_tracking_record
            with get_session(write=True) as session:
                MessageTrackingRecord.update(session, user.id, account.id, status=MessageTrackingStatus.STOPPED)

            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/message/tracking/stop", json={
                "account_id": account.id,
            })

            assert response.status_code == 400
