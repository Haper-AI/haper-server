from typing import Optional
from biz.service.db import get_session
from biz.dal.user import User
from biz.utils.response import ResponseCode
from werkzeug.security import generate_password_hash, check_password_hash

def signup_user_by_credential(email: str, password: str):
    # check user registered or not
    with get_session(write=True) as session:
        user = User.get_user_by_email(session, email)
        if user:
            raise ResponseCode.InvalidParam.create_error("Email already registered.")

        # extract name from email
        name = email.split('@')[0]

        # hashing user password
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

        user = User.add(session, name, email, hashed_password)
    return user


def signup_user_by_oauth(provider: str, provider_account_id: str, email: str,
                         access_token: str, refresh_token: Optional[str], expires_at: Optional[int]):
    raise NotImplementedError


def login_user_with_credential(email: str, password: str):
    session = get_session()
    user = User.get_user_by_email(session, email)
    if not user:
        raise ResponseCode.InvalidParam.create_error("Invalid email or password.")

    if not user.password:
        raise ResponseCode.InvalidParam.create_error("User not registered by credential.")

    # verifying password
    if not check_password_hash(user.password, password):
        raise ResponseCode.InvalidParam.create_error("Invalid email or password.")

    return user


def login_user_by_oauth(provider: str, provider_account_id: str, email: str,
                        access_token: str, refresh_token: Optional[str],
                        expires_at: Optional[int]):
    raise NotImplementedError
