from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import make_transient

from app.jobs.delete_marked_deleted_report import init_job, job_main
from biz.dal.report import Report
from biz.dal.user import User
from biz.service.db import get_session
from tests import generate_random_gmail


def test_delete_marked_deleted_report():
    with get_session(write=True) as session:
        # Create a report with deleted_at set to 31 days ago
        user = User.add(session, "user name", generate_random_gmail(8), email_verified=True)
        report = Report.add(
            session,
            user.id,
            {}
        )
        report.deleted_at = datetime.now(timezone.utc) - timedelta(days=31)
        report_id = report.id

    # Run the job
    init_job()
    job_main()

    # Check if the report was deleted
    with get_session(write=False) as session:
        deleted_report = Report.get_by_id(session, report_id)

    assert deleted_report is None
