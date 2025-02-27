from typing import List

from sqlalchemy.orm import make_transient

from biz.dal.user_setting import UserSetting
from biz.service.db import get_session
from biz.utils.response import ResponseCode


def get_user_setting(user_id: str):
    with get_session(write=False) as session:
        user_setting = UserSetting.get_by_user_id(session, user_id)

    return user_setting


def new_user_setting(user_id: str, key_message_tags: List[str]):
    with get_session(write=True) as session:
        user_setting = UserSetting.get_by_user_id(session, user_id)
        if user_setting:
            raise ResponseCode.UnsupportedAction.create_error("user setting already exist")

        user_setting = UserSetting.add(session, user_id, key_message_tags)

        make_transient(user_setting)

    return user_setting


def update_user_setting(user_id: str, key_message_tags: List[str]):
    with get_session(write=True) as session:
        user_setting = UserSetting.get_by_user_id(session, user_id)
        if not user_setting:
            raise ResponseCode.UnsupportedAction.create_error("user setting does not exist")

        UserSetting.update(session, user_id, key_message_tags)
        make_transient(user_setting)

    user_setting.key_message_tags = key_message_tags
    return user_setting