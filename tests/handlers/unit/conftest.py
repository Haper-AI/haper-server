from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy.orm import make_transient

from biz.dal.user import User, Account
from biz.service.db import get_session
from tests import generate_random_gmail, generate_random_string
from tests.handlers.conf_factory import new_handler_test_conf

app, client, runner = new_handler_test_conf(
    scope="module",
    db_name="tests-haper-unit",
    sqs_queue_name="test-unit-report-update",
)

@pytest.fixture
def new_user():
    email = generate_random_gmail(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email, email_verified=True)
        make_transient(user)

    return user


@pytest.fixture
def new_user_account():
    email = generate_random_gmail(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email, email_verified=True)
        account = Account.add(session, user.id, "google", generate_random_string(16),
                              "access_token", "refresh_token",
                              expires_at=int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()))

        make_transient(user), make_transient(account)

    return user, account