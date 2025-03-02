from uuid import UUID
from biz.service.db import get_session
from biz.dal.report import Report

def generate_new_report(user_id: UUID, filters: Optional[Dict] = None):
    with get_session(write=False) as session:
        try:
            latest_report = Report.get_latest_report(session, user_id)

            if latest_report and latest_report.content.get("status") == "generating":
                target_report = latest_report
            else:
                target_report = Report.create_blank_report(session, user_id)

            report_content = {
                "summary": "Recent activity summary",
                "stats": {"essential": 18, "non_essential": 7},
                "status": "completed"
            }

            target_report.content = report_content
            session.flush()

            new_blank = Report.create_blank_report(session, user_id)
            return target_report

        except Exception as e:
            session.rollback()
            raise RuntimeError(f"Report generation failed: {str(e)}")

def get_newest_report_summary(user_id: UUID):
    with get_session(write=False) as session:
        return Report.get_newest_by_user(session, user_id)

def list_history_reports(user_id: UUID):
    with get_session(write=False) as session:
        return Report.list_by_user(session, user_id)