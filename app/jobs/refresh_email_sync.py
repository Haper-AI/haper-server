from datetime import datetime, timedelta

from biz.controller.gmail_util import GmailAPIClient
from biz.controller.outlook_util import OutlookAPIClient
from biz.dal.message_tracking import MessageTrackingRecord, MessageTrackingStatus, MessageTrackingStatusExtraInfoKeys
from biz.dal.user import AccountProvider, Account
from biz.service.db import init_db, get_session


def init_job():
    init_db()


def job_main():
    limit = 5
    offset = 0
    has_db_records = True
    while has_db_records:
        with get_session(write=False) as session:
            message_tracking_records = session.query(MessageTrackingRecord).filter_by(
                status=MessageTrackingStatus.ONGOING,
            ).offset(offset).limit(limit).all()

        for record in message_tracking_records:
            if record.account_provider == AccountProvider.Google:
                if int((datetime.now() + timedelta(days=6)).timestamp()) > record.extra_info[
                    MessageTrackingStatusExtraInfoKeys.Expiration]:
                    # rewatch gmail

                    # gmail recommend to call watch once per day: https://developers.google.com/workspace/gmail/api/guides/push#renewing_mailbox_watch
                    with get_session(write=True) as session:
                        account = Account.get_by_id(session, record.account_id)
                        gmail_api_client = GmailAPIClient(account.access_token, account.refresh_token,
                                                          account.expires_at)
                        new_extra_info = record.extra_info
                        _, new_expiration = gmail_api_client.watch_gmail()
                        # update db
                        # TODO: there maybe some concurrent update problem with message sync
                        MessageTrackingRecord.update_extra_info_subfield(
                            session, record.user_id, record.account_id,
                            MessageTrackingStatusExtraInfoKeys.Expiration,
                            new_expiration
                        )
                        if gmail_api_client.access_token != account.access_token:
                            Account.update(
                                session,
                                account.id,
                                gmail_api_client.access_token,
                                expires_at=gmail_api_client.expires_at,
                            )
            elif record.account_provider == AccountProvider.Microsoft:
                if int((datetime.now() + timedelta(days=1)).timestamp()) > record.extra_info[
                    MessageTrackingStatusExtraInfoKeys.Expiration]:
                    # rewatch outlook
                    with get_session(write=True) as session:
                        account = Account.get_by_id(session, record.account_id)
                        outlook_api_client = OutlookAPIClient(account.access_token, account.refresh_token,
                                                              account.expires_at)
                        new_extra_info = record.extra_info
                        new_expiration = outlook_api_client.refresh_watch_outlook(
                            record.extra_info[MessageTrackingStatusExtraInfoKeys.SubscriptionID])
                        new_extra_info[MessageTrackingStatusExtraInfoKeys.Expiration] = new_expiration
                        # update db
                        MessageTrackingRecord.update(session, record.user_id, record.account_id,
                                                     extra_info=new_extra_info)

                        if outlook_api_client.access_token != account.access_token:
                            Account.update(
                                session,
                                account.id,
                                outlook_api_client.access_token,
                                outlook_api_client.refresh_token,
                                outlook_api_client.expires_at,
                            )

        # check if we have more records to process
        has_db_records = len(message_tracking_records) > 0
        offset += len(message_tracking_records)


if __name__ == '__main__':
    init_job()
    job_main()
