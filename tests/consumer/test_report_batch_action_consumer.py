from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from sqlalchemy.orm import make_transient

from app.consumer_main import handle_report_batch_action
from biz.controller.gmail_util import GmailAPIClient
from biz.controller.outlook_util import OutlookAPIClient
from biz.dal.user import AccountProvider
from biz.dal.report import MessageAction, MessageCategory, Report, ReportStatus
from biz.dal.report_batch_action import ReportBatchAction
from biz.dal.user import User, Account
from biz.service.db import get_session
from biz.model.report import report as report_model
from biz.model.report.report_batch_action_message import ReportBatchActionMessage
from tests import generate_random_string, generate_random_gmail, generate_random_outlook_email


@pytest.fixture(scope='module')
def patch_gmail_api():
    mock_gmail_client = MagicMock()

    mock_gmail_client.users().messages().modify.return_value.execute = MagicMock()
    mock_gmail_client.users().messages().trash.return_value.execute = MagicMock()
    mock_gmail_client.users().messages().send.return_value.execute = MagicMock()

    mock_credential = MagicMock()
    mock_credential.token = generate_random_string(10)
    mock_credential.expiry = datetime.now() + timedelta(hours=2)

    with patch.object(GmailAPIClient, "client", create=True, new_callable=PropertyMock) as p1:
        with patch.object(GmailAPIClient, "credential", create=True, new_callable=PropertyMock) as p2:
            p1.return_value = mock_gmail_client
            p2.return_value = mock_credential
            yield p1, p2


@pytest.fixture(scope='module')
def patch_outlook_api():
    mock_outlook_client = MagicMock()

    async def mock_read_email(*args):
        return None

    async def mock_trash_email():
        return None

    async def mock_reply_email_text(*args):
        return None

    mock_outlook_client.me.messages.by_message_id.return_value.patch = mock_read_email
    mock_outlook_client.me.messages.by_message_id.return_value.delete = mock_trash_email
    mock_outlook_client.me.messages.by_message_id.return_value.reply.post = mock_reply_email_text

    mock_credential = MagicMock()
    mock_credential.access_token = generate_random_string(10)
    mock_credential.refresh_token = generate_random_string(10)
    mock_credential.expires_at = int((datetime.now() + timedelta(hours=2)).timestamp())

    with patch.object(OutlookAPIClient, "client", create=True, new_callable=PropertyMock) as p1:
        with patch.object(OutlookAPIClient, "credential", create=True, new_callable=PropertyMock) as p2:
            p1.return_value = mock_outlook_client
            p2.return_value = mock_credential
            yield p1, p2


@pytest.fixture
def new_user_report():
    email_1 = generate_random_gmail(8)
    email_2 = generate_random_outlook_email(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email_1, email_verified=True)
        account_1 = Account.add(
            session, user.id, AccountProvider.Google, generate_random_string(16),
            "access_token", "refresh_token",
            expires_at=int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            email=email_1
        )
        account_2 = Account.add(
            session, user.id, AccountProvider.Microsoft, generate_random_string(16),
            "access_token", "refresh_token",
            expires_at=int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            email=email_2
        )
        report_obj = report_model.Report(
            messages_in_queue={},
            summary=[],
            content=report_model.ReportContent(
                content_sources=["gmail", "outlook"],
                gmail=[
                    report_model.MailMessagesByAccount(
                        account_id=str(account_1.id),
                        email=email_1,
                        messages=[
                            report_model.MailMessageItem(
                                id=0,
                                action=MessageAction.Read,
                                action_result=None,
                                message_id="message_id_0",
                                thread_id="thread_id_0",
                                receive_at=datetime.now(timezone.utc),
                                sender=generate_random_gmail(8),
                                subject="subject",
                                summary="some summary",
                                category=MessageCategory.Essential,
                                tags=["tag1", "tag2"],
                                reply_message=None
                            ),
                            report_model.MailMessageItem(
                                id=1,
                                action=MessageAction.Reply,
                                action_result=None,
                                message_id="message_id_1",
                                thread_id="thread_id_1",
                                receive_at=datetime.now(timezone.utc),
                                sender=generate_random_gmail(8),
                                subject="subject",
                                summary="some summary",
                                category=MessageCategory.Essential,
                                tags=["tag1", "tag2"],
                                reply_message="some reply message",
                            ),
                            report_model.MailMessageItem(
                                id=2,
                                action=MessageAction.Delete,
                                action_result=None,
                                message_id="message_id_2",
                                thread_id="thread_id_2",
                                receive_at=datetime.now(timezone.utc),
                                sender=generate_random_gmail(8),
                                subject="subject",
                                summary="some summary",
                                category=MessageCategory.NonEssential,
                                tags=["tag1", "tag2"],
                                reply_message=None
                            )
                        ]
                    )
                ],
                outlook=[
                    report_model.MailMessagesByAccount(
                        account_id=str(account_2.id),
                        email=email_2,
                        messages=[
                            report_model.MailMessageItem(
                                id=3,
                                action=MessageAction.Read,
                                action_result=None,
                                message_id="message_id_0",
                                thread_id="thread_id_0",
                                receive_at=datetime.now(timezone.utc),
                                sender=generate_random_outlook_email(8),
                                subject="subject",
                                summary="some summary",
                                category=MessageCategory.Essential,
                                tags=["tag1", "tag2"],
                                reply_message=None
                            ),
                            report_model.MailMessageItem(
                                id=4,
                                action=MessageAction.Reply,
                                action_result=None,
                                message_id="message_id_1",
                                thread_id="thread_id_1",
                                receive_at=datetime.now(timezone.utc),
                                sender=f'{generate_random_string(5)} <{generate_random_outlook_email(8)}>',
                                subject="subject",
                                summary="some summary",
                                category=MessageCategory.Essential,
                                tags=["tag1", "tag2"],
                                reply_message="some reply message",
                            ),
                            report_model.MailMessageItem(
                                id=5,
                                action=MessageAction.Delete,
                                action_result=None,
                                message_id="message_id_2",
                                thread_id="thread_id_2",
                                receive_at=datetime.now(timezone.utc),
                                sender=generate_random_outlook_email(8),
                                subject="subject",
                                summary="some summary",
                                category=MessageCategory.NonEssential,
                                tags=["tag1", "tag2"],
                                reply_message=None
                            )
                        ]
                    )
                ]
            )
        )
        report = Report.add(session, user.id, report_obj.to_dict())
        Report.update(session, user.id, status=ReportStatus.Finalized)

        batch_run = ReportBatchAction.add(session, report.id, 6)

        make_transient(report), make_transient(batch_run)

    return report, batch_run


@pytest.mark.usefixtures('patch_gmail_api')
@pytest.mark.usefixtures('patch_outlook_api')
def test_handle_report_batch_action(patch_gmail_api, new_user_report):
    report, batch_run = new_user_report
    handle_report_batch_action(ReportBatchActionMessage(str(report.id), str(batch_run.id)))
