from enum import Enum
from app.jobs.delete_marked_deleted_report import handler as delete_marked_deleted_report_handler
from app.jobs.delete_marked_deleted_user import handler as delete_marked_deleted_user_handler
from app.jobs.finalize_report import handler as finalize_report_handler
from app.jobs.refresh_email_sync import handler as refresh_email_sync_handler


class JobType(str, Enum):
    DeleteMarkedDeletedReport = "DeleteMarkedDeletedReport"
    DeleteMarkedDeletedUser = "DeleteMarkedDeletedUser"
    FinalizeReport = "FinalizeReport"
    RefreshEmailSync = "RefreshEmailSync"


def handler(event, context):
    job_type = event["job_type"]
    if job_type == JobType.DeleteMarkedDeletedReport:
        delete_marked_deleted_report_handler(event, context)
    elif job_type == JobType.DeleteMarkedDeletedUser:
        delete_marked_deleted_user_handler(event, context)
    elif job_type == JobType.FinalizeReport:
        finalize_report_handler(event, context)
    elif job_type == JobType.RefreshEmailSync:
        refresh_email_sync_handler(event, context)
