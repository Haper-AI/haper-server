from sqlalchemy.orm import Session, make_transient

from biz.model.report.report import report_from_dict
from biz.service.db import get_session
from biz.dal.report import Report, ReportStatus
from biz.utils.response import ResponseCode
from biz.model.report import report as report_model

def init_report_content():
    return report_model.Report(summary=[], content=report_model.ReportContent([], None))


def start_new_reporting_sequence(session: Session, user_id: str):
    latest_report = Report.get_latest_by_user_id(session, user_id)
    if latest_report:
        raise ResponseCode.UnsupportedAction.create_error("already started reporting sequence")

    # create a new blank report
    Report.add(session, user_id, {})


def end_reporting_sequence(session: Session, user_id: str):
    latest_report = Report.get_latest_by_user_id(session, user_id)
    if not latest_report:
        raise ResponseCode.UnsupportedAction.create_error("reporting sequence already ended")
    if not latest_report.content: # if latest report doesn't have content, delete it directly
        Report.delete(session, latest_report.id)
    else:
        Report.update(session, latest_report.id, status=ReportStatus.Finalized)


def generate_report(user_id: str):
    with get_session(write=True) as session:
        latest_report = Report.get_latest_by_user_id(session, user_id)
        if latest_report and not latest_report.content:
            raise ResponseCode.UnsupportedAction.create_error(
                "latest report has no content, please wait for new messages")
        # finalize the report and create a new one
        Report.update(session, latest_report.id, status=ReportStatus.Finalized)
        blank_report = Report.add(session, user_id, {})
        make_transient(latest_report), make_transient(blank_report)

    return latest_report, blank_report


def get_newest_report_summary(user_id: str):
    with get_session(write=False) as session:
        latest_report = Report.get_latest_by_user_id(session, user_id)

    if latest_report and latest_report.content:
        report_content = report_from_dict(latest_report.content)
        if report_content.summary:
            return [r.to_dict() for r in report_content.summary]
    return []


def list_history_reports(user_id: str):
    with get_session(write=False) as session:
        return Report.list_by_user(session, user_id)
