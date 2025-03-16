import time
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy.orm import make_transient

from biz.dal.report import Report, ReportStatus, MessageCategory, MessageAction
from biz.dal.report_batch_action import ReportBatchAction, MessageActionResult, BatchActionRunStatus
from biz.dal.user import User, Account
from biz.handler.middleware import gen_jwt_auth
from biz.service.db import get_session
from biz.model.report import report as report_model
from biz.model.report import rich_text as rich_text_model
from biz.utils.env import RuntimeEnv
from biz.model.report import action_log as action_log_model

from tests import generate_random_gmail, generate_random_string


@pytest.fixture
def new_user_empty_report():
    email = generate_random_gmail(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email, email_verified=True)
        account = Account.add(
            session, user.id, "google", generate_random_string(16),
            "access_token", "refresh_token",
            expires_at=int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            email=email
        )
        report = Report.add(session, user.id, {})
        make_transient(user), make_transient(account), make_transient(report)
    return user, account, report


@pytest.fixture
def new_user_report():
    email = generate_random_gmail(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email, email_verified=True)
        account = Account.add(
            session, user.id, "google", generate_random_string(16),
            "access_token", "refresh_token",
            expires_at=int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            email=email
        )
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
                    email=rich_text_model.Email(email=email, name="email name"),
                    annotations=rich_text_model.Annotations(
                        bold=True,
                    ),
                )
            ],
            content=report_model.ReportContent(
                content_sources=["gmail"],
                gmail=[
                    report_model.MailMessagesByAccount(
                        account_id=str(account.id),
                        email=email,
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
                ]
            )
        )
        report = Report.add(session, user.id, report_obj.to_dict())

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
        account = Account.add(
            session, user.id, "google", generate_random_string(16),
            "access_token", "refresh_token",
            expires_at=int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            email=email
        )
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
                    email=rich_text_model.Email(email=email, name="email name"),
                    annotations=rich_text_model.Annotations(
                        bold=True,
                    ),
                )
            ],
            content=report_model.ReportContent(
                content_sources=["gmail"],
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
                ]
            )
        )
        report = Report.add(session, user.id, report_obj.to_dict())
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
        account = Account.add(
            session, user.id, "google", generate_random_string(16),
            "access_token", "refresh_token",
            expires_at=int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            email=email
        )
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
                    email=rich_text_model.Email(email=email, name="email name"),
                    annotations=rich_text_model.Annotations(
                        bold=True,
                    ),
                )
            ],
            content=report_model.ReportContent(
                content_sources=["gmail"],
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
                ]
            )
        )
        report = Report.add(session, user.id, report_obj.to_dict())
        Report.update(session, report.id, status=ReportStatus.Finalized)

        make_transient(user), make_transient(account), make_transient(report)

    return user, account, report


@pytest.fixture
def new_user_report_with_messages_in_queue():
    email = generate_random_gmail(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email, email_verified=True)
        account = Account.add(
            session, user.id, "google", generate_random_string(16),
            "access_token", "refresh_token",
            expires_at=int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            email=email
        )
        report_obj = report_model.Report(
            messages_in_queue={
                "gmail": 4
            },
            summary=[],
            content=report_model.ReportContent(
                content_sources=[],
                gmail=None
            )
        )
        report = Report.add(session, user.id, report_obj.to_dict())
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
        response = client.put("/api/v1/report/{}".format(report.id), json={
            "gmail": {
                str(account.id): [
                    {
                        "id": 0,
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
                        "id": 1,
                        "action": MessageAction.Delete,
                        "category": MessageCategory.NonEssential,
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


@pytest.fixture(scope="module")
def patch_thread():
    with patch('threading.Thread', return_value=MagicMock()) as patch_thread:
        yield patch_thread


class TestReportBatchAction:
    @pytest.mark.usefixtures("patch_thread")
    def test_success(self, client, new_user_report):
        user, _, report = new_user_report
        with get_session(write=True) as session:
            Report.update(session, report.id, status=ReportStatus.Finalized)
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))

        response = client.post("/api/v1/report/{}/batch-action".format(report.id))
        assert response.status_code == 200

    class TestFail:
        def test_fail_with_invalid_auth(self, client, new_user_report):
            user, _, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(uuid.uuid4())))
            response = client.post("/api/v1/report/{}/batch-action".format(report.id))
            assert response.status_code == 400

        def test_fail_with_invalid_report_status(self, client, new_user_report):
            user, _, report = new_user_report
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
        response = client.get("/api/v1/report/{}/batch-action-status".format(report.id))
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

    class TestFail:
        def test_fail_with_invalid_auth(self, client, new_user_report):
            user, _, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(uuid.uuid4())))
            response = client.get("/api/v1/report/{}/batch-action-status".format(report.id))
            assert response.status_code == 400

        def test_fail_with_no_run_info(self, client, new_user_report):
            user, _, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.get("/api/v1/report/{}/batch-action-status".format(report.id))
            assert response.status_code == 400


class TestGenerateMessageReply:
    def test_success(self, client, new_user_report):
        pass

    class TestFail:
        pass
