import base64
from datetime import datetime, timezone, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy.orm import make_transient

from biz.dal.user import User, Account, AccountProvider
from biz.service.db import get_session
from tests import generate_random_gmail, generate_random_string, generate_random_outlook_email
from tests.handlers.conf_factory import new_handler_test_conf

app, client, runner = new_handler_test_conf(
    scope="module",
    db_name="tests-haper-unit",
    sqs_queue_name="test-unit-async-action",
)


@pytest.fixture
def new_user():
    email = generate_random_gmail(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email, email_verified=True)
        make_transient(user)

    return user


def db_add_new_account(session, user_id, email, provider: str):
    account = Account.add(
        session, user_id, provider, generate_random_string(16),
        "access_token", "refresh_token",
        expires_at=int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        email=email)
    return account


@pytest.fixture
def new_user_gmail_account():
    email = generate_random_gmail(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email, email_verified=True)
        account = db_add_new_account(session, user.id, email, AccountProvider.Google)
        make_transient(user), make_transient(account)

    return user, account


@pytest.fixture
def new_user_outlook_account():
    email = generate_random_outlook_email(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email, email_verified=True)
        account = db_add_new_account(session, user.id, email, AccountProvider.Microsoft)
        make_transient(user), make_transient(account)

    return user, account


def create_rsa_pairs():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

    # Serialize private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # Generate public key
    public_key = private_key.public_key()

    # Serialize public key
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    return private_pem.decode(), public_pem.decode()
