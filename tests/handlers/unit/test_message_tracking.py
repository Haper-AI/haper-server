import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy.orm import make_transient

from biz.dal.message_tracking import MessageTrackingRecord, MessageTrackingStatus
from biz.dal.report import Report
from biz.dal.user import Account, User
from biz.handler.middleware import gen_jwt_auth
from biz.service.db import get_session
from biz.utils.env import RuntimeEnv

from tests import generate_random_string, generate_random_gmail
from .conftest import client, new_user, new_user_account


@pytest.fixture
def new_user_account_tracking_record():
    email = generate_random_gmail(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email, email_verified=True)
        account = Account.add(session, user.id, "google", generate_random_string(16),
                              "access_token", "refresh_token",
                              expires_at=int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()))

        record = MessageTrackingRecord.add(session, str(user.id), str(account.id), extra_info={
            "some_info_key": "some_info_value"
        })
        Report.add(session, user.id, {})

        make_transient(user), make_transient(account), make_transient(record)
    return user, account, record


@pytest.fixture(scope="module")
def patch_build_gmail_client():
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


class TestMessageTrackingGetStatus:
    def test_success(self, client, new_user_account_tracking_record):
        user, _, _ = new_user_account_tracking_record
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
        response = client.get("/api/v1/message/tracking/status")
        assert response.status_code == 200
        assert len(response.get_json()['data']['tracking_status']) != 0


class TestMessageTrackingStart:
    class TestSuccess:
        @pytest.mark.usefixtures("patch_build_gmail_client")
        def test_success_by_exist_google_account(self, client, new_user_account):
            user, account = new_user_account
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/message/tracking/start", json={
                "account_id": account.id,
            })

            assert response.status_code == 200
            assert response.get_json()['data']['new_tracking_status']

        @pytest.mark.usefixtures("patch_build_gmail_client")
        def test_success_by_new_google_account(self, client, new_user):
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(new_user.id)))
            response = client.post("/api/v1/message/tracking/start", json={
                "account": {
                    "provider": "google",
                    "provider_account_id": generate_random_string(16),
                    "access_token": "access_token",
                    "refresh_token": "refresh_token",
                    "expires_at": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
                    "email": "email",
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

        def test_fail_by_invalid_status(self, client, new_user_account_tracking_record):
            user, _, _ = new_user_account_tracking_record
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/message/tracking/start", json={
                "account_id": str(uuid.uuid4()),
            })

            assert response.status_code == 400


class TestMessageTrackingStop:

    @pytest.mark.usefixtures("patch_build_gmail_client")
    def test_success(self, client, new_user_account_tracking_record):
        user, account, _ = new_user_account_tracking_record
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

        def test_fail_by_no_tracking_configured(self, client, new_user_account):
            user, account = new_user_account
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/message/tracking/stop", json={
                "account_id": account.id,
            })

            assert response.status_code == 400

        def test_fail_by_invalid_tracking_status(self, client, new_user_account_tracking_record):
            user, account, record = new_user_account_tracking_record
            with get_session(write=True) as session:
                MessageTrackingRecord.update(session, user.id, account.id, status=MessageTrackingStatus.STOPPED)

            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/message/tracking/stop", json={
                "account_id": account.id,
            })

            assert response.status_code == 400
