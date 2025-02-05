import base64
import os
from typing import Optional

from cryptography.exceptions import InvalidKey

from biz.service.db import get_session
from biz.dal.user import User, Account
from biz.utils.response import ResponseCode
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from sqlalchemy.orm import make_transient

email_to_name = lambda email: email.split('@')[0]


def hash_password(password: str, salt: bytes = None) -> str:
    if not salt:
        salt = os.urandom(16)
    hashed = Scrypt(salt=salt, length=32, n=32768, r=8, p=1).derive(password.encode())
    return f'{base64.b64encode(salt).decode()}${base64.b64encode(hashed).decode()}'


def compare_password(hashed_password: str, password: str) -> bool:
    salt, hashed = hashed_password.split('$', 1)
    try:
        (Scrypt(salt=base64.b64decode(salt), length=32, n=32768, r=8, p=1)
         .verify(password.encode(), base64.b64decode(hashed)))
        return True
    except InvalidKey:
        return False


def signup_user_by_credential(email: str, password: str):
    # check user registered or not
    with get_session(write=True) as session:
        user = User.get_by_email(session, email)
        if user:
            raise ResponseCode.InvalidParam.create_error("Email already registered.")

        # extract name from email
        name = email_to_name(email)

        # hashing user password
        hashed_password = hash_password(password)

        user = User.add(session, name, email, password=hashed_password)
        make_transient(user)
    return user


def signup_user_by_oauth(provider: str, provider_account_id: str, email: str,
                         access_token: str, refresh_token: Optional[str], expires_at: Optional[int],
                         name: Optional[str], image: Optional[str]):
    with get_session(write=True) as session:
        account = Account.get_by_provider_and_provider_id(session, provider, provider_account_id)
        if account:
            raise ResponseCode.InvalidParam.create_error(f"{provider} account already registered.")

        if not name:
            name = email_to_name(email)
        user = User.add(session, name, email, email_verified=True, image=image)
        account = Account.add(session, user.id, provider, provider_account_id,
                              email, access_token, refresh_token, expires_at)
        make_transient(user), make_transient(account)
    return user, account


def login_user_with_credential(email: str, password: str):
    with get_session(write=False) as session:
        user = User.get_by_email(session, email)

    if not user:
        raise ResponseCode.InvalidParam.create_error("Invalid email or password.")

    if not user.password:
        raise ResponseCode.InvalidParam.create_error("User not registered by credential.")

    # verifying password
    if not compare_password(user.password, password):
        raise ResponseCode.InvalidParam.create_error("Invalid email or password.")

    return user


def login_user_by_oauth(provider: str, provider_account_id: str,
                        access_token: str, refresh_token: Optional[str],
                        expires_at: Optional[int]):
    with get_session(write=True) as session:
        account = Account.get_by_provider_and_provider_id(session, provider, provider_account_id)
        if not account:
            raise ResponseCode.InvalidParam.create_error(f"{provider} account not registered.")

        user = User.get_by_id(session, account.user_id)
        if not user:
            raise ResponseCode.InternalUnknownError.create_error(f"user not found for account {provider_account_id}")

        # update account
        Account.update_tokens(session, provider, provider_account_id, access_token, refresh_token, expires_at)

        make_transient(user)
    return user