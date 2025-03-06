from sqlalchemy.orm import Session, make_transient

from biz.service.db import get_session
from biz.dal.report import Report, ReportStatus
from biz.utils.response import ResponseCode
from biz.model.report import report as report_model


def start_new_reporting_sequence(session: Session, user_id: str):
    latest_report = Report.get_latest_by_user_id(session, user_id)
    if latest_report:
        raise ResponseCode.UnsupportedAction.create_error("already started reporting sequence")

    # create a new blank report
    Report.add(session, user_id, {})


def end_reporting_sequence(session: Session, user_id: str):
    latest_report = Report.get_latest_by_user_id(session, user_id, for_update=True)
    if not latest_report:
        raise ResponseCode.UnsupportedAction.create_error("reporting sequence already ended")
    if not latest_report.content: # if latest report doesn't have content, delete it directly
        Report.delete(session, latest_report.id)
    else:
        # has content, finalize report
        Report.update(session, latest_report.id, status=ReportStatus.Finalized)


def generate_report(user_id: str):
    with get_session(write=True) as session:
        latest_report = Report.get_latest_by_user_id(session, user_id, for_update=True)
        if latest_report and not latest_report.content:
            raise ResponseCode.UnsupportedAction.create_error(
                "latest report has no content, please wait for new messages")
        # finalize the report and create a new one
        Report.update(session, latest_report.id, status=ReportStatus.Finalized)
        blank_report = Report.add(session, user_id, {})
        make_transient(latest_report), make_transient(blank_report)

    return latest_report, blank_report


def get_newest_report(user_id: str):
    with get_session(write=False) as session:
        latest_report = Report.get_latest_by_user_id(session, user_id)
    return latest_report


def list_history_reports(user_id: str):
    with get_session(write=False) as session:
        return Report.list_by_user(session, user_id)

def get_report_by_id(user_id: str, report_id: str):
    with get_session(write=False) as session:
        report = Report.get_by_id(session, report_id)

    if not report or report.is_deleted:
        raise ResponseCode.ResourceNotFound.create_error("report not found")

    if str(report.user_id) != user_id:
        raise ResponseCode.UnsupportedAction.create_error("current user does not has permission for this report")
    return report

def delete_report_by_id(user_id: str, report_id: str):
    with get_session(write=True) as session:
        report = Report.get_by_id(session, report_id, for_update=True)

        if not report or report.is_deleted:
            raise ResponseCode.ResourceNotFound.create_error("report not found")

        if str(report.user_id) != user_id:
            raise ResponseCode.UnsupportedAction.create_error("current user does not has permission for this report")

        if report.status == ReportStatus.Appending:
            raise ResponseCode.UnsupportedAction.create_error("current report is still processing incoming messages")

        Report.mark_deleted(session, report_id)