import base64
import random
import time
import uuid
from datetime import datetime, timezone, timedelta
from email.utils import formatdate
from unittest.mock import patch, MagicMock, PropertyMock

import pytest
from sqlalchemy.orm import make_transient

from biz.controller.gmail_util import GmailAPIClient
from biz.dal.user import AccountProvider
from biz.dal.email import Email, EmailSource
from biz.dal.report import Report, ReportStatus, MessageCategory, MessageAction, ReportType
from biz.dal.report_batch_action import ReportBatchAction, MessageActionResult, BatchActionRunStatus
from biz.dal.user import User
from biz.dal.user_subscription import UserSubscription
from biz.handler.middleware import gen_jwt_auth
from biz.utils.report import ReportFieldName
from biz.service.db import get_session
from haper_script.schema_gen.python import report as report_model
from haper_script.schema_gen.python import rich_text as rich_text_model
from biz.utils.env import RuntimeEnv
from haper_script.schema_gen.python import action_log as action_log_model

from tests import generate_random_gmail, generate_random_string
from tests.handlers.unit.conftest import db_add_new_account
from .conftest import new_user_gmail_account

embeddings = [random.uniform(-1, 1) for _ in range(768)]


@pytest.fixture
def new_user_empty_report():
    email = generate_random_gmail(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email, email_verified=True)
        account = db_add_new_account(session, user.id, email, provider=AccountProvider.Google)
        report = Report.add(session, user.id, ReportType.Realtime, {})
        make_transient(user), make_transient(account), make_transient(report)
    return user, account, report


@pytest.fixture
def new_user_report():
    email = generate_random_gmail(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email, email_verified=True)
        account = db_add_new_account(session, user.id, email, provider=AccountProvider.Google)
        message_ids = [generate_random_string(8) for _ in range(3)]
        emails = [
            Email(
                user_id=user.id,
                source=EmailSource.Gmail,
                message_id=message_ids[0],
                thread_id=message_ids[0],
                sender=generate_random_gmail(8),
                receiver=generate_random_gmail(8),
                subject="subject",
                receive_at=datetime.now(timezone.utc),
                tags=["tag1", "tag2"],
                summary="some summary",
                summary_embedding=embeddings,
                llm_category=MessageCategory.Essential,
                llm_action=MessageAction.Read,
            ),
            Email(
                user_id=user.id,
                source=EmailSource.Gmail,
                message_id=message_ids[1],
                thread_id=message_ids[1],
                sender=generate_random_gmail(8),
                receiver=generate_random_gmail(8),
                subject="subject",
                receive_at=datetime.now(timezone.utc),
                tags=["tag1", "tag2"],
                summary="some summary",
                summary_embedding=embeddings,
                llm_category=MessageCategory.Essential,
                llm_action=MessageAction.Reply,
                reply_message="some reply message",
            ),
            Email(
                user_id=user.id,
                source=EmailSource.Gmail,
                message_id=message_ids[2],
                thread_id=message_ids[2],
                sender=generate_random_gmail(8),
                receiver=generate_random_gmail(8),
                subject="subject",
                receive_at=datetime.now(timezone.utc),
                tags=["tag1", "tag2"],
                summary="some summary",
                summary_embedding=embeddings,
                llm_category=MessageCategory.NonEssential,
                llm_action=MessageAction.Delete,
            )
        ]
        session.add_all(emails)
        session.flush()
        report_obj = report_model.Report(
            messages_in_queue={},
            summary=[
                report_model.RichText(
                    type=rich_text_model.TypeEnum.TEXT,
                    text=rich_text_model.Text("this is a text"),
                    email=None,
                    annotations=None,
                ),
                report_model.RichText(
                    type=rich_text_model.TypeEnum.EMAIL,
                    text=None,
                    email=rich_text_model.Email(address=email, name="email name"),
                    annotations=rich_text_model.Annotations(
                        bold=True,
                    ),
                )
            ],
            content=report_model.ReportContent(
                content_sources=[EmailSource.Gmail],
                gmail=[
                    report_model.MailMessagesByAccount(
                        account_id=str(account.id),
                        email=email,
                        messages=[
                            report_model.MailMessageItem(
                                id=emails[0].id,
                                action=emails[0].llm_action,
                                action_result=None,
                                message_id=emails[0].message_id,
                                thread_id=emails[0].thread_id,
                                receive_at=emails[0].receive_at,
                                sender=emails[0].sender,
                                subject=emails[0].subject,
                                summary=emails[0].summary,
                                category=emails[0].llm_category,
                                tags=emails[0].tags,
                                reply_message=emails[0].reply_message,
                            ),
                            report_model.MailMessageItem(
                                id=emails[1].id,
                                action=emails[1].llm_action,
                                action_result=None,
                                message_id=emails[1].message_id,
                                thread_id=emails[1].thread_id,
                                receive_at=emails[1].receive_at,
                                sender=emails[1].sender,
                                subject=emails[1].subject,
                                summary=emails[1].summary,
                                category=emails[1].llm_category,
                                tags=emails[1].tags,
                                reply_message=emails[1].reply_message,
                            ),
                            report_model.MailMessageItem(
                                id=emails[2].id,
                                action=emails[2].llm_action,
                                action_result=None,
                                message_id=emails[2].message_id,
                                thread_id=emails[2].thread_id,
                                receive_at=emails[2].receive_at,
                                sender=emails[2].sender,
                                subject=emails[2].subject,
                                summary=emails[2].summary,
                                category=emails[2].llm_category,
                                tags=emails[2].tags,
                                reply_message=emails[2].reply_message,
                            )
                        ]
                    )
                ],
                outlook=None
            )
        )
        report = Report.add(session, user.id, ReportType.Realtime, report_obj.to_dict())

        make_transient(user), make_transient(account), make_transient(report)

    return user, account, report


@pytest.fixture
def new_user_report_with_done_action():
    """
    report status will be finalized
    :return:
    """
    email = generate_random_gmail(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email, email_verified=True)
        account = db_add_new_account(session, user.id, email, provider=AccountProvider.Google)
        report_obj = report_model.Report(
            messages_in_queue={},
            summary=[
                report_model.RichText(
                    type=rich_text_model.TypeEnum.TEXT,
                    text=rich_text_model.Text("this is a text"),
                    email=None,
                    annotations=None,
                ),
                report_model.RichText(
                    type=rich_text_model.TypeEnum.EMAIL,
                    text=None,
                    email=rich_text_model.Email(address=email, name="email name"),
                    annotations=rich_text_model.Annotations(
                        bold=True,
                    ),
                )
            ],
            content=report_model.ReportContent(
                content_sources=[EmailSource.Gmail],
                gmail=[
                    report_model.MailMessagesByAccount(
                        account_id=str(account.id),
                        email=email,
                        messages=[
                            report_model.MailMessageItem(
                                id=0,
                                action=MessageAction.Read,
                                action_result=MessageActionResult.Success,
                                message_id="message_id_0",
                                thread_id="thread_id_0",
                                receive_at=datetime.now(timezone.utc),
                                sender=generate_random_gmail(8),
                                subject="subject",
                                summary="some summary",
                                category=MessageCategory.Essential,
                                tags=["tag1", "tag2"],
                                reply_message=None
                            )
                        ]
                    )
                ],
                outlook=None,
            )
        )
        report = Report.add(session, user.id, ReportType.Realtime, report_obj.to_dict())
        Report.update(session, report.id, status=ReportStatus.Finalized)

        make_transient(user), make_transient(account), make_transient(report)

    return user, account, report


@pytest.fixture
def new_user_report_with_reply_action_and_no_reply_message():
    """
    report status will be finalized
    :return:
    """
    email = generate_random_gmail(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email, email_verified=True)
        account = db_add_new_account(session, user.id, email, provider=AccountProvider.Google)
        report_obj = report_model.Report(
            messages_in_queue={},
            summary=[
                report_model.RichText(
                    type=rich_text_model.TypeEnum.TEXT,
                    text=rich_text_model.Text("this is a text"),
                    email=None,
                    annotations=None,
                ),
                report_model.RichText(
                    type=rich_text_model.TypeEnum.EMAIL,
                    text=None,
                    email=rich_text_model.Email(address=email, name="email name"),
                    annotations=rich_text_model.Annotations(
                        bold=True,
                    ),
                )
            ],
            content=report_model.ReportContent(
                content_sources=[EmailSource.Gmail],
                gmail=[
                    report_model.MailMessagesByAccount(
                        account_id=str(account.id),
                        email=email,
                        messages=[
                            report_model.MailMessageItem(
                                id=0,
                                action=MessageAction.Reply,
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
                            )
                        ]
                    )
                ],
                outlook=None
            )
        )
        report = Report.add(session, user.id, ReportType.Realtime, report_obj.to_dict())
        Report.update(session, report.id, status=ReportStatus.Finalized)

        make_transient(user), make_transient(account), make_transient(report)

    return user, account, report


@pytest.fixture
def new_user_report_with_messages_in_queue():
    email = generate_random_gmail(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email, email_verified=True)
        account = db_add_new_account(session, user.id, email, provider=AccountProvider.Google)
        report_obj = report_model.Report(
            messages_in_queue={
                "gmail": 4
            },
            summary=[],
            content=report_model.ReportContent(
                content_sources=[],
                gmail=None,
                outlook=None,
            )
        )
        report = Report.add(session, user.id, ReportType.Realtime, report_obj.to_dict())
        Report.update(session, report.id, status=ReportStatus.Finalized)

        make_transient(user), make_transient(account), make_transient(report)

    return user, account, report


class TestGetNewestReport:
    class TestSuccess:
        def test_success_with_empty_report(self, client, new_user_empty_report):
            user, _, report = new_user_empty_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.get("/api/v1/report/newest")
            assert response.status_code == 200
            assert response.get_json()['data']['report']

        def test_success_with_report(self, client, new_user_report):
            user, _, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.get("/api/v1/report/newest")
            assert response.status_code == 200
            assert response.get_json()['data']['report']


class TestGenerateReport:
    def test_success(self, client, new_user_report):
        user, _, report = new_user_report
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
        response = client.post("/api/v1/report/generate")
        assert response.status_code == 200
        assert response.get_json()['data']['report']

    class TestFail:
        def test_fail_with_no_content(self, client, new_user_empty_report):
            user, _, report = new_user_empty_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/report/generate")
            assert response.status_code == 400

        def test_fail_with_reach_limit(self, client, new_user_report):
            user, _, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))

            for _ in range(10):
                response = client.post("/api/v1/report/generate")
                assert response.status_code == 200

                with get_session(write=True) as session:
                    new_report = Report.get_latest_by_user_id(session, user.id, ReportType.Realtime)
                    Report.delete(session, new_report.id)
                    Report.update(session, report.id, status=ReportStatus.Appending)

            # third request
            response = client.post("/api/v1/report/generate")
            assert response.status_code == 400


class TestListReportHistory:
    def test_success(self, client, new_user_report):
        user, _, report = new_user_report
        with get_session(write=True) as session:
            Report.update(session, report.id, status=ReportStatus.Finalized)
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
        response = client.get("/api/v1/report/history")
        assert response.status_code == 200
        assert response.get_json()['data']['reports']


class TestGetReportById:
    def test_success(self, client, new_user_report):
        user, _, report = new_user_report
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
        response = client.get("/api/v1/report/{}".format(report.id))
        assert response.status_code == 200
        assert response.get_json()['data']['report']

    class TestFail:
        def test_fail_with_invalid_auth(self, client, new_user_report):
            user, _, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(uuid.uuid4())))
            response = client.get("/api/v1/report/{}".format(report.id))
            assert response.status_code == 400

        def test_fail_with_non_exist_report(self, client, new_user):
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(new_user.id)))
            response = client.get("/api/v1/report/{}".format(uuid.uuid4()))
            assert response.status_code == 404


class TestPollMessageProcessingStatus:
    class TestSuccess:
        def test_success_with_messages_in_queue(self, client, new_user_report_with_messages_in_queue):
            user, _, report = new_user_report_with_messages_in_queue
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/report/{}/message-processing-status".format(report.id))
            with get_session(write=True) as session:
                Report.update_content_subfield(session, report.id, ReportFieldName.MessagesInQueue, {"gmail": 0})
            assert response.status_code == 200
            assert 'text/event-stream' in response.headers['Content-Type']
            assert response.data

        def test_success_without_messages_in_queue(self, client, new_user_empty_report):
            user, _, report = new_user_empty_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/report/{}/message-processing-status".format(report.id))
            assert response.status_code == 200
            assert 'text/event-stream' in response.headers['Content-Type']
            assert response.data

    class TestFail:
        def test_fail_with_invalid_auth(self, client, new_user_empty_report):
            user, _, report = new_user_empty_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(uuid.uuid4())))
            response = client.post("/api/v1/report/{}/message-processing-status".format(report.id))
            assert response.status_code == 400

        def test_fail_with_non_exist_report(self, client, new_user_empty_report):
            user, _, report = new_user_empty_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/report/{}/message-processing-status".format(str(uuid.uuid4())))
            assert response.status_code == 404


class TestDeleteReport:
    def test_success(self, client, new_user_report):
        user, _, report = new_user_report
        with get_session(write=True) as session:
            Report.update(session, report.id, status=ReportStatus.Finalized)
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
        response = client.delete("/api/v1/report/{}".format(report.id))
        assert response.status_code == 200

    class TestFail:
        def test_fail_with_invalid_auth(self, client, new_user_report):
            user, _, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(uuid.uuid4())))
            response = client.delete("/api/v1/report/{}".format(report.id))
            assert response.status_code == 400

        def test_fail_with_non_exist_report(self, client, new_user):
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(new_user.id)))
            response = client.delete("/api/v1/report/{}".format(uuid.uuid4()))
            assert response.status_code == 404

        def test_fail_with_invalid_report_status(self, client, new_user_report):
            user, _, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.delete("/api/v1/report/{}".format(report.id))
            assert response.status_code == 400


class TestUpdateReport:
    def test_success(self, client, new_user_report):
        user, account, report = new_user_report
        with get_session(write=True) as session:
            Report.update(session, report.id, status=ReportStatus.Finalized)
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
        report_obj = report_model.Report.from_dict(report.content)
        response = client.put("/api/v1/report/{}".format(report.id), json={
            "gmail": {
                str(account.id): [
                    {
                        "id": report_obj.content.gmail[0].messages[0].id,
                        "action": MessageAction.Reply,
                        "category": MessageCategory.Essential,
                        "reply_message": """
                        Dear xxx,
                        
                        This is the reply body
                        
                        Best regards,
                        Somebody
                        """
                    },
                    {
                        "id": report_obj.content.gmail[0].messages[1].id,
                        "action": MessageAction.Delete,
                        "category": MessageCategory.NonEssential,
                    },
                    {
                        "id": report_obj.content.gmail[0].messages[2].id,
                        "category": MessageCategory.Essential,
                    }
                ]
            }
        })
        assert response.status_code == 200

        with get_session(write=False) as session:
            report = Report.get_by_id(session, report.id)
        report_obj = report_model.report_from_dict(report.content)

        assert report_obj.content.gmail[0].messages[0].action == MessageAction.Reply
        assert report_obj.content.gmail[0].messages[0].category == MessageCategory.Essential
        assert report_obj.content.gmail[0].messages[1].action == MessageAction.Delete

    class TestFail:
        def test_fail_with_invalid_auth(self, client, new_user_report):
            user, account, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(uuid.uuid4())))
            response = client.put("/api/v1/report/{}".format(report.id), json={
                "gmail": {
                    str(account.id): []
                }
            })
            assert response.status_code == 400

        def test_fail_with_empty_updates(self, client, new_user_report):
            user, account, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.put("/api/v1/report/{}".format(report.id), json={
                "gmail": {}
            })
            assert response.status_code == 400

            response = client.put("/api/v1/report/{}".format(report.id), json={
                "gmail": {
                    str(account.id): []
                }
            })
            assert response.status_code == 400

        def test_fail_with_invalid_report_status(self, client, new_user_report):
            user, account, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.put("/api/v1/report/{}".format(report.id), json={
                "gmail": {
                    str(account.id): [
                        {
                            "id": 1,
                            "action": MessageAction.Read,
                            "category": MessageCategory.NonEssential,
                        }
                    ]
                }
            })
            assert response.status_code == 400

        def test_fail_with_invalid_batch_action_status(self, client, new_user_report):
            user, account, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            with get_session(write=True) as session:
                Report.update(session, report.id, status=ReportStatus.Finalized)
                ReportBatchAction.add(session, report.id, 3)
            response = client.put("/api/v1/report/{}".format(report.id), json={
                "gmail": {
                    str(account.id): [
                        {
                            "id": 1,
                            "action": MessageAction.Read,
                            "category": MessageCategory.NonEssential,
                        }
                    ]
                }
            })
            assert response.status_code == 400

        def test_fail_with_no_correspond_item(self, client, new_user_report):
            user, account, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            with get_session(write=True) as session:
                Report.update(session, report.id, status=ReportStatus.Finalized)

            response = client.put("/api/v1/report/{}".format(report.id), json={
                "gmail": {
                    str(account.id): [
                        {
                            "id": 9999,
                            "action": MessageAction.Read,
                            "category": MessageCategory.NonEssential,
                        }
                    ]
                }
            })
            assert response.status_code == 400

            response = client.put("/api/v1/report/{}".format(report.id), json={
                "gmail": {
                    str(uuid.uuid4()): [
                        {
                            "id": 1,
                            "action": MessageAction.Read,
                            "category": MessageCategory.NonEssential,
                        }
                    ]
                }
            })
            assert response.status_code == 400

        def test_fail_with_no_content(self, client, new_user_empty_report):
            user, account, report = new_user_empty_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            with get_session(write=True) as session:
                Report.update(session, report.id, status=ReportStatus.Finalized)
            response = client.put("/api/v1/report/{}".format(report.id), json={
                "gmail": {
                    str(account.id): [
                        {
                            "id": 0,
                            "action": MessageAction.Read,
                            "category": MessageCategory.NonEssential,
                        }
                    ]
                }
            })
            assert response.status_code == 400

        def test_fail_with_invalid_action_result(self, client, new_user_report_with_done_action):
            user, account, report = new_user_report_with_done_action
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.put("/api/v1/report/{}".format(report.id), json={
                "gmail": {
                    str(account.id): [
                        {
                            "id": 0,
                            "action": MessageAction.Read,
                            "category": MessageCategory.NonEssential,
                        }
                    ]
                }
            })
            assert response.status_code == 400


class TestReportBatchAction:
    def test_success(self, client, new_user_report):
        user, _, report = new_user_report
        with get_session(write=True) as session:
            Report.update(session, report.id, status=ReportStatus.Finalized)
            UserSubscription.add(session, str(user.id), generate_random_string(20),
                                 generate_random_string(20), "month", "active")
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))

        response = client.post("/api/v1/report/{}/batch-action".format(report.id))
        assert response.status_code == 200

    class TestFail:
        def test_fail_with_invalid_auth(self, client, new_user_report):
            user, _, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(uuid.uuid4())))
            response = client.post("/api/v1/report/{}/batch-action".format(report.id))
            assert response.status_code == 400

        def test_fail_with_no_subscription(self, client, new_user_report):
            user, _, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/report/{}/batch-action".format(report.id))
            assert response.status_code == 400

        def test_fail_with_invalid_report_status(self, client, new_user_report):
            user, _, report = new_user_report
            with get_session(write=True) as session:
                UserSubscription.add(session, str(user.id), generate_random_string(20),
                                     generate_random_string(20), "month", "active")
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/report/{}/batch-action".format(report.id))
            assert response.status_code == 400

        def test_fail_with_invalid_batch_action_status(self, client, new_user_report):
            user, _, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            with get_session(write=True) as session:
                Report.update(session, report.id, status=ReportStatus.Finalized)
                ReportBatchAction.add(session, report.id, 3)
            response = client.post("/api/v1/report/{}/batch-action".format(report.id))
            assert response.status_code == 400

        def test_fail_with_messages_in_queue(self, client, new_user_report_with_messages_in_queue):
            user, _, report = new_user_report_with_messages_in_queue
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/report/{}/batch-action".format(report.id))
            assert response.status_code == 400

        def test_fail_with_no_content(self, client, new_user_empty_report):
            user, _, report = new_user_empty_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            with get_session(write=True) as session:
                Report.update(session, report.id, status=ReportStatus.Finalized)
            response = client.post("/api/v1/report/{}/batch-action".format(report.id))
            assert response.status_code == 400

        def test_fail_with_no_action(self, client, new_user_report_with_done_action):
            user, _, report = new_user_report_with_done_action
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/report/{}/batch-action".format(report.id))
            assert response.status_code == 400

        def test_fail_with_no_reply_message_for_reply_action(
                self,
                client,
                new_user_report_with_reply_action_and_no_reply_message
        ):
            user, _, report = new_user_report_with_reply_action_and_no_reply_message
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/report/{}/batch-action".format(report.id))
            assert response.status_code == 400


class TestPollReportRunStatus:
    def test_success(self, client, new_user_report):
        user, _, report = new_user_report
        with get_session(write=True) as session:
            Report.update(session, report.id, status=ReportStatus.Finalized)
            run = ReportBatchAction.add(session, report.id, 3)
            make_transient(run)

        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
        response = client.post("/api/v1/report/{}/batch-action-status".format(report.id))
        assert response.status_code == 200
        assert 'text/event-stream' in response.headers['Content-Type']

        for i in range(3):
            time.sleep(1)
            with get_session(write=True) as session:
                ReportBatchAction.append_logs(session, run.id, [
                    action_log_model.ActionLog(
                        id=i,
                        at=int(datetime.now().timestamp()),
                        message="done {}".format(i),
                    ).to_dict()
                ])
        with get_session(write=True) as session:
            ReportBatchAction.update(session, run.id, BatchActionRunStatus.Done)

        assert response.data

    def test_success_with_no_run_info(self, client, new_user_report):
        user, _, report = new_user_report
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
        response = client.post("/api/v1/report/{}/batch-action-status".format(report.id))
        assert response.status_code == 200

    class TestFail:
        def test_fail_with_invalid_auth(self, client, new_user_report):
            user, _, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(uuid.uuid4())))
            response = client.post("/api/v1/report/{}/batch-action-status".format(report.id))
            assert response.status_code == 400


@pytest.fixture(scope="module")
def patch_gmail_get_message():
    mock_gmail_client = MagicMock()

    def mock_get_message(*args):
        # email data 1
        return {
            "snippet": "some snippet",
            "labelIds": [
                "CATEGORY_PROMOTIONS",
                "IMPORTANT",
            ],
            "payload": {
                "headers": [
                    {
                        "name": "Date",
                        "value": formatdate(timeval=datetime.now().timestamp(), localtime=True, usegmt=False),
                    },
                    {
                        "name": "Subject",
                        "value": "some subject",
                    },
                    {
                        "name": "From",
                        "value": "some one <someone@gmail.com>",
                    },
                    {
                        "name": "To",
                        "value": "receiver@gmail.com"
                    }
                ],
                "mimeType": "text/plain",
                "body": {
                    "size": 20,
                    "data": base64.urlsafe_b64encode("Some email body data".encode("utf-8")).decode("utf-8")
                }
            }
        }

    mock_gmail_client.users().messages().get.return_value.execute = mock_get_message

    mock_credential = MagicMock()
    mock_credential.token = generate_random_string(10)
    mock_credential.expiry = datetime.now() + timedelta(hours=2)
    with patch.object(GmailAPIClient, "client", create=True, new_callable=PropertyMock) as p1:
        with patch.object(GmailAPIClient, "credential", create=True, new_callable=PropertyMock) as p2:
            p1.return_value = mock_gmail_client
            p2.return_value = mock_credential
            yield p1, p2


@pytest.fixture(scope="module")
def patch_langchain_chat_model():
    mock_chat_model = MagicMock()

    def chat_model_streaming(*args):
        for i in range(10):
            tmp = MagicMock()
            tmp.content = "message-{}".format(i)
            yield tmp
            time.sleep(0.4)

    mock_chat_model.stream = chat_model_streaming

    with patch('biz.controller.report.init_chat_model', return_value=mock_chat_model) as mock_init_chat_model:
        yield mock_init_chat_model


class TestGenerateMessageReply:
    @pytest.mark.usefixtures("patch_gmail_get_message")
    @pytest.mark.usefixtures("patch_langchain_chat_model")
    def test_success(self, client, new_user_report):
        user, account, report = new_user_report
        with get_session(write=True) as session:
            UserSubscription.add(session, str(user.id), generate_random_string(20),
                                 generate_random_string(20), "month", "active")
            Report.update(session, report.id, status=ReportStatus.Finalized)

            # insert similar email as reply history
            session.add_all([
                Email(
                    user_id=user.id,
                    source="gmail",
                    message_id="message-id-1",
                    thread_id="thread-id-1",
                    sender="some one <someone@gmail.com>",
                    receiver="receiver@gmail.com",
                    subject="some subject",
                    receive_at=datetime.now(timezone.utc),
                    tags=["tag1", "tag2"],
                    summary="some summary",
                    summary_embedding=embeddings,
                    llm_category=MessageCategory.Essential,
                    llm_action=MessageAction.Reply,
                    reply_message="Some reply message 1"
                ),
                Email(
                    user_id=user.id,
                    source="gmail",
                    message_id="message-id-2",
                    thread_id="thread-id-2",
                    sender="some one <someone@gmail.com>",
                    receiver="receiver@gmail.com",
                    subject="some subject",
                    receive_at=datetime.now(timezone.utc),
                    tags=["tag3", "tag4"],
                    summary="some summary",
                    summary_embedding=embeddings,
                    llm_category=MessageCategory.Essential,
                    llm_action=MessageAction.Reply,
                    reply_message="Some reply message 2"
                ),
            ])

        report_obj = report_model.Report.from_dict(report.content)
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
        response = client.post("/api/v1/report/{}/generate-reply".format(report.id), json={
            "source": "gmail",
            "account_id": str(account.id),
            "id": report_obj.content.gmail[0].messages[1].id
        })
        assert response.status_code == 200
        assert 'text/event-stream' in response.headers['Content-Type']
        assert response.data

    class TestFail:
        def test_fail_with_invalid_auth(self, client, new_user_report):
            user, _, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(uuid.uuid4())))
            response = client.post("/api/v1/report/{}/generate-reply".format(report.id))
            assert response.status_code == 400

        def test_fail_with_invalid_report_status(self, client, new_user_report):
            user, account, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/report/{}/generate-reply".format(report.id), json={
                "source": "gmail",
                "account_id": str(account.id),
                "id": 1
            })
            assert response.status_code == 400

        def test_fail_with_invalid_batch_action_status(self, client, new_user_report):
            user, account, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            with get_session(write=True) as session:
                Report.update(session, report.id, status=ReportStatus.Finalized)
                ReportBatchAction.add(session, report.id, 3)
            response = client.post("/api/v1/report/{}/generate-reply".format(report.id), json={
                "source": "gmail",
                "account_id": str(account.id),
                "id": 1
            })
            assert response.status_code == 400

        def test_fail_with_no_content(self, client, new_user_empty_report):
            user, account, report = new_user_empty_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            with get_session(write=True) as session:
                Report.update(session, report.id, status=ReportStatus.Finalized)
            response = client.post("/api/v1/report/{}/generate-reply".format(report.id), json={
                "source": "gmail",
                "account_id": str(account.id),
                "id": 1
            })
            assert response.status_code == 400

        def test_fail_with_not_reply_action(self, client, new_user_report_with_done_action):
            user, account, report = new_user_report_with_done_action
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/report/{}/batch-action".format(report.id), json={
                "source": "gmail",
                "account_id": str(account.id),
                "id": 0
            })
            assert response.status_code == 400


class TestGetMessageContent:
    @pytest.mark.usefixtures("patch_gmail_get_message")
    def test_success(self, client, new_user_report):
        user, account, report = new_user_report
        report_obj = report_model.Report.from_dict(report.content)
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
        response = client.get("/api/v1/report/{}/message-content".format(report.id), query_string={
            "source": "gmail",
            "account_id": str(account.id),
            "id": report_obj.content.gmail[0].messages[0].id
        })
        assert response.status_code == 200
        assert response.data


class TestGeneratePreviousReport:
    def test_success(self, client, new_user_gmail_account):
        user, account = new_user_gmail_account
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))

        response = client.post("/api/v1/report/previous/generate", json={
            "email_list_to_process": [
                {
                    "account_id": str(account.id),
                    "number_of_email": 10
                }
            ]
        })

        assert response.status_code == 200
        assert response.get_json()['data']['report']
        assert response.get_json()['data']['message'] == "Previous report generation initiated successfully"

        # Verify the report was created
        report_data = response.get_json()['data']['report']
        assert report_data['id']
        assert report_data['status'] == ReportStatus.Appending

    def test_success_multiple_accounts(self, client, new_user_gmail_account):
        user, account = new_user_gmail_account

        # Create a second account
        with get_session(write=True) as session:
            account2 = db_add_new_account(session, user.id, generate_random_gmail(8), provider=AccountProvider.Google)
            make_transient(account2)

        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))

        response = client.post("/api/v1/report/previous/generate", json={
            "email_list_to_process": [
                {
                    "account_id": str(account.id),
                    "number_of_email": 5
                },
                {
                    "account_id": str(account2.id),
                    "number_of_email": 15
                }
            ]
        })

        assert response.status_code == 200
        assert response.get_json()['data']['report']

    class TestFail:
        def test_fail_with_invalid_auth(self, client, new_user_gmail_account):
            user, account = new_user_gmail_account
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(uuid.uuid4())))

            response = client.post("/api/v1/report/previous/generate", json={
                "email_list_to_process": [
                    {
                        "account_id": str(account.id),
                        "number_of_email": 10
                    }
                ]
            })

            assert response.status_code == 400

        def test_fail_with_invalid_account_id(self, client, new_user_gmail_account):
            user, account = new_user_gmail_account
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))

            response = client.post("/api/v1/report/previous/generate", json={
                "email_list_to_process": [
                    {
                        "account_id": str(uuid.uuid4()),
                        "number_of_email": 10
                    }
                ]
            })

            assert response.status_code == 400

        def test_fail_with_too_many_emails(self, client, new_user_gmail_account):
            user, account = new_user_gmail_account
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))

            response = client.post("/api/v1/report/previous/generate", json={
                "email_list_to_process": [
                    {
                        "account_id": str(account.id),
                        "number_of_email": 150
                    }
                ]
            })

            assert response.status_code == 400

        def test_fail_with_empty_email_list(self, client, new_user_gmail_account):
            user, account = new_user_gmail_account
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))

            response = client.post("/api/v1/report/previous/generate", json={
                "email_list_to_process": []
            })

            assert response.status_code == 400

        def test_fail_with_missing_fields(self, client, new_user_gmail_account):
            user, account = new_user_gmail_account
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))

            # Missing number_of_email
            response = client.post("/api/v1/report/previous/generate", json={
                "email_list_to_process": [
                    {
                        "account_id": str(account.id)
                    }
                ]
            })

            assert response.status_code == 400

            # Missing account_id
            response = client.post("/api/v1/report/previous/generate", json={
                "email_list_to_process": [
                    {
                        "number_of_email": 10
                    }
                ]
            })

            assert response.status_code == 400

        def test_fail_with_existing_previous_report_task(self, client, new_user_gmail_account):
            user, account = new_user_gmail_account

            # Create an existing previous report
            with get_session(write=True) as session:
                Report.add(session, user.id, ReportType.Previous, {})

            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.post("/api/v1/report/previous/generate", json={
                "email_list_to_process": [
                    {
                        "account_id": str(account.id),
                        "number_of_email": 10
                    }
                ]
            })

            assert response.status_code == 400
            assert "already exists an task" in response.get_json()['message']

        def test_fail_with_rate_limit(self, client, new_user_gmail_account):
            user, account = new_user_gmail_account
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))

            # Make 5 successful requests (the daily limit)
            for i in range(5):
                response = client.post("/api/v1/report/previous/generate", json={
                    "email_list_to_process": [
                        {
                            "account_id": str(account.id),
                            "number_of_email": 10
                        }
                    ]
                })

                if response.status_code == 200:
                    # Clean up the created report to allow next request
                    with get_session(write=True) as session:
                        latest_report = Report.get_latest_by_user_id(session, user.id, ReportType.Previous)
                        if latest_report:
                            Report.delete(session, latest_report.id)

            # The 6th request should be rate limited
            response = client.post("/api/v1/report/previous/generate", json={
                "email_list_to_process": [
                    {
                        "account_id": str(account.id),
                        "number_of_email": 10
                    }
                ]
            })

            assert response.status_code == 400
