from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import make_transient

from app.jobs.finalize_report import init_job, job_main
from biz.dal.report import Report, ReportStatus
from biz.dal.user import User
from biz.dal.user_setting import UserSetting, DEFAULT_REPORT_MAX_TIME_DURATION
from biz.service.db import get_session
from tests import generate_random_gmail


def test_finalize_report():
    with get_session(write=True) as session:
        # Create a user and a report
        user = User.add(session, "user name", generate_random_gmail(8), email_verified=True)
        UserSetting.add(session, user.id, report_max_duration=DEFAULT_REPORT_MAX_TIME_DURATION)
        report = Report.add(
            session,
            user.id,
            {}
        )
        report.created_at = datetime.now(timezone.utc) - timedelta(seconds=DEFAULT_REPORT_MAX_TIME_DURATION+10)
        report_id = report.id

    # Run the job
    init_job()
    job_main()

    # Check if the report was finalized
    with get_session(write=False) as session:
        finalized_report = Report.get_by_id(session, report_id)

    assert finalized_report is not None
    assert finalized_report.status == ReportStatus.Finalized
    assert finalized_report.finalized_at is not None
