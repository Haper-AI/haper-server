import uuid

import pytest
from sqlalchemy.orm import make_transient

from biz.dal.user import User
from biz.dal.user_setting import UserSetting
from biz.handler.middleware import gen_jwt_auth
from biz.service.db import get_session
from biz.utils.env import RuntimeEnv
from .conftest import client, new_user
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


class TestSetUserSetting:
    def test_success(self, client, new_user):
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(new_user.id)))
        tags = ["Newsletter"]
        response = client.post("/api/v1/user/setting", json={"key_message_tags": tags})

        assert response.status_code == 200
        assert response.get_json()['data']['setting']['key_message_tags'] == tags


    class TestFail:
        def test_fail_by_already_set(self, client, new_user_setting):
            user, setting = new_user_setting
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/user/setting", json={"key_message_tags": ["Newsletter"]})
            assert response.status_code == 400


class TestUpdateUserSetting:
    def test_success(self, client, new_user_setting):
        user, setting = new_user_setting
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
        tags = ["Newsletter"]
        response = client.put("/api/v1/user/setting", json={"key_message_tags": tags})
        assert response.status_code == 200
        assert response.get_json()['data']['setting']['key_message_tags'] == tags

    class TestFail:
        def test_fail_by_no_setting(self, client, new_user):
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(new_user.id)))
            response = client.put("/api/v1/user/setting", json={"key_message_tags": ["Newsletter"]})
            assert response.status_code == 400