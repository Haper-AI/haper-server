from datetime import datetime, timezone, timedelta

from app.jobs.delete_marked_deleted_report import init_job, job_main
from biz.dal.email import EmailSource, Email
from biz.dal.report import Report, MessageAction, MessageCategory
from biz.dal.user import User
from biz.model.report import report as report_model
from biz.service.db import get_session
from tests import generate_random_gmail


def test_delete_marked_deleted_report():
    report_obj = report_model.Report(
        summary=[],
        messages_in_queue={
            "gmail": 0,
            "outlook": 0
        },
        content=report_model.ReportContent(
            content_sources=[EmailSource.Gmail, EmailSource.Outlook],
            gmail=[
                report_model.MailMessagesByAccount(
                    account_id="account_id_1",
                    email=generate_random_gmail(8),
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
    with get_session(write=True) as session:
        # Create a report with deleted_at set to 31 days ago
        user = User.add(session, "user name", generate_random_gmail(8), email_verified=True)
        report = Report.add(
            session,
            user.id,
            report_obj.to_dict()
        )
        email = Email(
            id=0,
            user_id=user.id,
            source=EmailSource.Gmail,
            message_id="message_id_0",
            thread_id="thread_id_0",
            sender=generate_random_gmail(8),
            receiver=generate_random_gmail(8),
            subject="subject",
            receive_at=datetime.now(timezone.utc),
            tags=["tag1", "tag2"],
            summary="some summary",
            llm_category=MessageCategory.Essential,
            llm_action=MessageAction.Reply,
        )
        session.add(email)
        report.deleted_at = datetime.now(timezone.utc) - timedelta(days=31)
        report_id = report.id

    # Run the job
    init_job()
    job_main()

    # Check if the report was deleted
    with get_session(write=False) as session:
        deleted_report = Report.get_by_id(session, report_id)

    assert deleted_report is None
