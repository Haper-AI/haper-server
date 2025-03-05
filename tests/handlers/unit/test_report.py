from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import make_transient

from biz.dal.report import Report, ReportStatus
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
        r = report_model.Report(
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
                gmail=report_model.Gmail(
                    essential=[
                        report_model.MailReportItem(
                            action="read",
                            message_id="message_id_0",
                            thread_id="thread_id_0",
                            receive_at=datetime.now(timezone.utc),
                            sender=generate_random_gmail(8),
                            subject="subject",
                            summary="some summary",
                            tags=["tag1", "tag2"]
                        ),
                        report_model.MailReportItem(
                            action="reply",
                            message_id="message_id_1",
                            thread_id="thread_id_1",
                            receive_at=datetime.now(timezone.utc),
                            sender=generate_random_gmail(8),
                            subject="subject",
                            summary="some summary",
                            tags=["tag1", "tag2"]
                        ),
                    ],
                    non_essential=[
                        report_model.MailReportItem(
                            action="delete",
                            message_id="message_id_2",
                            thread_id="thread_id_2",
                            receive_at=datetime.now(timezone.utc),
                            sender=generate_random_gmail(8),
                            subject="subject",
                            summary="some summary",
                            tags=["tag1", "tag2"]
                        )
                    ]
                )
            )
        )
        report = Report.add(session, user.id, r.to_dict())

        make_transient(user), make_transient(report)

    return user, report

class TestGetNewestReportSummary:
    class TestSuccess:
        def test_success_with_empty_report(self, client, new_user_empty_report):
            user, report = new_user_empty_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.get("/api/v1/report/newest_summary")
            assert response.status_code == 200
            assert response.get_json()['data']['summary'] == []

        def test_success_with_report(self, client, new_user_report):
            user, report = new_user_report
            client.set_cookie(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME, gen_jwt_auth(str(user.id)))
            response = client.get("/api/v1/report/newest_summary")
            assert response.status_code == 200
            assert response.get_json()['data']['summary']


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

