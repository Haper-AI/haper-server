import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import make_transient

from biz.dal.report import Report, ReportStatus, MessageCategory
from biz.dal.user import User
from biz.handler.middleware import gen_jwt_auth
from biz.service.db import get_session
from biz.model.report import report as report_model
from biz.model.report import rich_text as rich_text_model
from biz.utils.env import RuntimeEnv

from tests import generate_random_gmail


@pytest.fixture
def new_user_empty_report():
    email = generate_random_gmail(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email, email_verified=True)
        report = Report.add(session, user.id, {})
        make_transient(user), make_transient(report)
    return user, report


@pytest.fixture
def new_user_report():
    email = generate_random_gmail(8)
    with get_session(write=True) as session:
        user = User.add(session, "user name", email, email_verified=True)
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
                    annotations=None,
                )
            ],
            content=report_model.ReportContent(
                content_sources=["gmail"],
                gmail=[
                    report_model.MailReportItem(
                        _id=0,
                        action="read",
                        message_id="message_id_0",
                        thread_id="thread_id_0",
                        receive_at=datetime.now(timezone.utc),
                        sender=generate_random_gmail(8),
                        subject="subject",
                        summary="some summary",
                        category=MessageCategory.Essential.value,
                        tags=["tag1", "tag2"]
                    ),
                    report_model.MailReportItem(
                        _id=1,
                        action="reply",
                        message_id="message_id_1",
                        thread_id="thread_id_1",
                        receive_at=datetime.now(timezone.utc),
                        sender=generate_random_gmail(8),
                        subject="subject",
                        summary="some summary",
                        category=MessageCategory.Essential.value,
                        tags=["tag1", "tag2"]
                    ),
                    report_model.MailReportItem(
                        _id=2,
                        action="delete",
                        message_id="message_id_2",
                        thread_id="thread_id_2",
                        receive_at=datetime.now(timezone.utc),
                        sender=generate_random_gmail(8),
                        subject="subject",
                        summary="some summary",
                        category=MessageCategory.NonEssential.value,
                        tags=["tag1", "tag2"]
                    )
                ]
            )
        )
        report = Report.add(session, user.id, report_obj.to_dict())

        make_transient(user), make_transient(report)

    return user, report


class TestGetNewestReport:
    class TestSuccess:
        def test_success_with_empty_report(self, client, new_user_empty_report):
            user, report = new_user_empty_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.get("/api/v1/report/newest")
            assert response.status_code == 200
            assert response.get_json()['data']['report']

        def test_success_with_report(self, client, new_user_report):
            user, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.get("/api/v1/report/newest")
            assert response.status_code == 200
            assert response.get_json()['data']['report']


class TestGenerateReport:
    def test_success(self, client, new_user_report):
        user, report = new_user_report
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
        response = client.post("/api/v1/report/generate")
        assert response.status_code == 200
        assert response.get_json()['data']['report']


class TestListReportHistory:
    def test_success(self, client, new_user_report):
        user, report = new_user_report
        with get_session(write=True) as session:
            Report.update(session, report.id, status=ReportStatus.Finalized)
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
        response = client.get("/api/v1/report/history")
        assert response.status_code == 200
        assert response.get_json()['data']['reports']


class TestGetReportById:
    def test_success(self, client, new_user_report):
        user, report = new_user_report
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
        response = client.get("/api/v1/report/{}".format(report.id))
        assert response.status_code == 200
        assert response.get_json()['data']['report']

    class TestFail:
        def test_fail_with_invalid_auth(self, client, new_user_report):
            user, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(uuid.uuid4())))
            response = client.get("/api/v1/report/{}".format(report.id))
            assert response.status_code == 400

        def test_fail_with_non_exist_report(self, client, new_user):
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(new_user.id)))
            response = client.get("/api/v1/report/{}".format(uuid.uuid4()))
            assert response.status_code == 404


class TestDeleteReport:
    def test_success(self, client, new_user_report):
        user, report = new_user_report
        with get_session(write=True) as session:
            Report.update(session, report.id, status=ReportStatus.Finalized)
        client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
        response = client.delete("/api/v1/report/{}".format(report.id))
        assert response.status_code == 200

    class TestFail:
        def test_fail_with_invalid_auth(self, client, new_user_report):
            user, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(uuid.uuid4())))
            response = client.delete("/api/v1/report/{}".format(report.id))
            assert response.status_code == 400

        def test_fail_with_non_exist_report(self, client, new_user):
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(new_user.id)))
            response = client.delete("/api/v1/report/{}".format(uuid.uuid4()))
            assert response.status_code == 404

        def test_fail_with_invalid_report_status(self, client, new_user_report):
            user, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.delete("/api/v1/report/{}".format(report.id))
            assert response.status_code == 400
