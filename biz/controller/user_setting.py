from typing import List, Optional

from sqlalchemy.orm import make_transient

from biz.controller.gmail_util import GmailAPIClient
from biz.controller.outlook_util import OutlookAPIClient
from biz.controller.report import end_reporting_sequence
from biz.dal.user import AccountProvider
from biz.dal.message_tracking import MessageTrackingStatus, MessageTrackingRecord, MessageTrackingStatusExtraInfoKeys
from biz.dal.user import Account, User
from biz.dal.user_setting import UserSetting
from biz.service.db import get_session
from biz.utils.logger import logger
from biz.utils.response import ResponseCode


def get_user_setting(user_id: str):
    with get_session(write=False) as session:
        user_setting = UserSetting.get_by_user_id(session, user_id)

    return user_setting


# def new_user_setting(user_id: str, key_message_tags: Optional[List[str]] = None,
#                      report_max_duration: Optional[int] = None):
#     with get_session(write=True) as session:
#         user_setting = UserSetting.get_by_user_id(session, user_id)
#         if user_setting:
#             raise ResponseCode.UnsupportedAction.create_error("user setting already exist")
#
#         user_setting = UserSetting.add(session, user_id, key_message_tags, report_max_duration)
#
#         make_transient(user_setting)
#
#     return user_setting


def update_user_setting(user_id: str, key_message_tags: Optional[List[str]] = None,
                        report_max_duration: Optional[int] = None):
    with get_session(write=True) as session:
        user_setting = UserSetting.get_by_user_id(session, user_id)
        if not user_setting:
            raise ResponseCode.UnsupportedAction.create_error("user setting does not exist")

        UserSetting.update(session, user_id, key_message_tags, report_max_duration)
        make_transient(user_setting)

    user_setting.key_message_tags = key_message_tags
    user_setting.report_max_duration = report_max_duration
    return user_setting


def delete_user(user_id: str):
    with get_session(write=True) as session:
        # end all message tracking for user
        message_tracking_statuses = MessageTrackingRecord.list_by_user_id(session, user_id, ongoing_only=True)
        for t in message_tracking_statuses:
            account = Account.get_by_id(session, t.account_id)
            try:
                if account.provider == AccountProvider.Google:
                    gmail_api_client = GmailAPIClient(
                        account.access_token,
                        account.refresh_token,
                        account.expires_at
                    )

                    gmail_api_client.stop_watch()
                elif account.provider == AccountProvider.Microsoft:
                    msgraph_api_client = OutlookAPIClient(
                        account.access_token,
                        account.refresh_token,
                        account.expires_at
                    )
                    msgraph_api_client.stop_watch_outlook(
                        t.extra_info[MessageTrackingStatusExtraInfoKeys.SubscriptionID])

                MessageTrackingRecord.update(session, t.user_id, t.account_id, status=MessageTrackingStatus.STOPPED)
            except Exception as e:
                logger.error("error happened when stop messaging: {}".format(str(e)))

        # end report sequence
        end_reporting_sequence(session, user_id)

        # mark user as delete
        User.mark_deleted(session, user_id)
