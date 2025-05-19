import uuid
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from sqlalchemy.orm import make_transient

from biz.controller.gmail_util import GmailAPIClient
from biz.controller.outlook_util import OutlookAPIClient
from biz.dal.message_tracking import MessageTrackingRecord
from biz.dal.report import Report
from biz.dal.user import User, AccountProvider
from biz.dal.user_setting import UserSetting
from biz.handler.middleware import gen_jwt_auth
from biz.service.db import get_session
from biz.utils.env import RuntimeEnv
from .conftest import client, new_user, db_add_new_account
from tests import generate_random_gmail


class TestGetUserInfo:
    def test_success(self, client, new_user):
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(new_user.id)))
        response = client.get("/api/v1/user/info")
        assert response.status_code == 200

    class TestFail:
        def test_fail_by_no_auth(self, client):
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, "")
            response = client.get("/api/v1/user/info")
            assert response.status_code == 401

        def test_fail_by_no_user(self, client):
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(uuid.uuid4())))
            response = client.get("/api/v1/user/info")
            assert response.status_code == 400


@pytest.fixture
def new_user_setting():
    email = generate_random_gmail(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email, email_verified=True)
        setting = UserSetting.add(session, user.id, ["Newsletter", "Job Offer", "Interview"])
        make_transient(user), make_transient(setting)

    return user, setting


class TestGetUserSetting:
    class TestSuccess:
        def test_success_with_setting(self, client, new_user_setting):
            user, setting = new_user_setting
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.get("/api/v1/user/setting")
            assert response.status_code == 200
            assert response.get_json()['data']['setting']['key_message_tags']

        def test_success_without_setting(self, client, new_user):
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(new_user.id)))
            response = client.get("/api/v1/user/setting")
            assert response.status_code == 200
            assert not response.get_json()['data']['setting']

    class TestFail:
        def test_fail_by_no_auth(self, client):
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, "")
            response = client.get("/api/v1/user/setting")
            assert response.status_code == 401


# class TestCreateUserSetting:
#     def test_success(self, client, new_user):
#         client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(new_user.id)))
#         tags = ["Newsletter"]
#         report_max_duration = 10000
#         response = client.post("/api/v1/user/setting", json={
#             "key_message_tags": tags,
#             "report_max_duration": report_max_duration
#         })
#
#         assert response.status_code == 200
#         assert response.get_json()['data']['setting']['key_message_tags'] == tags
#
#     class TestFail:
#         def test_fail_by_already_set(self, client, new_user_setting):
#             user, setting = new_user_setting
#             client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
#             response = client.post("/api/v1/user/setting", json={"key_message_tags": ["Newsletter"]})
#             assert response.status_code == 400


class TestUpdateUserSetting:
    def test_success(self, client, new_user_setting):
        user, setting = new_user_setting
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
        tags = ["Newsletter"]
        report_max_duration = 10000
        response = client.put("/api/v1/user/setting", json={
            "key_message_tags": tags,
            "report_max_duration": report_max_duration
        })
        assert response.status_code == 200
        assert response.get_json()['data']['setting']['key_message_tags'] == tags
        assert response.get_json()['data']['setting']['report_max_duration'] == report_max_duration

    class TestFail:
        def test_fail_by_no_setting(self, client, new_user):
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(new_user.id)))
            response = client.put("/api/v1/user/setting", json={"key_message_tags": ["Newsletter"]})
            assert response.status_code == 400


@pytest.fixture
def mock_gmail_and_outlook():
    async def delete_sub():
        return None

    mock_outlook_client = MagicMock()
    mock_outlook_client.subscriptions.by_subscription_id.return_value.delete = delete_sub

    with patch.object(GmailAPIClient, "client", create=True, new_callable=PropertyMock) as p1:
        with patch.object(GmailAPIClient, "credential", create=True, new_callable=PropertyMock) as p2:
            with patch.object(OutlookAPIClient, "client", create=True, new_callable=PropertyMock) as p3:
                with patch.object(OutlookAPIClient, "credential", create=True, new_callable=PropertyMock) as p4:
                    p3.return_value = mock_outlook_client
                    yield p1, p2, p3, p4


class TestDeleteUserSetting:
    @pytest.mark.usefixtures("mock_gmail_and_outlook")
    def test_success(self, client):
        email = generate_random_gmail(8)
        with get_session(write=True) as session:
            user = User.add(session, "user name", email, email_verified=True)
            account_1 = db_add_new_account(session, user.id, email, provider=AccountProvider.Google)
            account_2 = db_add_new_account(session, user.id, email, provider=AccountProvider.Microsoft)

            MessageTrackingRecord.add(session, user.id, account_1.id, account_1.provider, extra_info={})
            MessageTrackingRecord.add(session, user.id, account_2.id, account_2.provider, extra_info={
                "subscription_id": "subscription_id_1",
            })

            Report.add(session, user.id, {})
            make_transient(user)

        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
        response = client.delete("/api/v1/user")
        assert response.status_code == 200
        with get_session(write=False) as session:
            user = User.get_by_id(session, user.id)
        assert user.deleted_at is not None
