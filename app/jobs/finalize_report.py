from datetime import datetime, timedelta, timezone
from typing import Dict

from biz.dal.report import Report, ReportStatus
from biz.dal.user_setting import UserSetting
from biz.service.db import init_db, get_session
from biz.utils.logger import logger


def init_job():
    init_db()


def job_main():
    limit = 10
    offset = 0
    has_db_records = True
    while has_db_records:
        with get_session(write=False) as session:
            report_rows = session.query(Report.id, Report.user_id, Report.created_at).filter_by(
                status=ReportStatus.Appending,
            ).offset(offset).limit(limit).all()
            user_ids = [r[1] for r in report_rows]

            # get user settings
            user_setting_rows = session.query(UserSetting.user_id, UserSetting.report_max_duration).filter(
                UserSetting.user_id.in_(user_ids)
            ).all()

        # get report that should be finalized
        report_by_user_id: Dict[str, Report] = {}
        for r in report_rows:
            report_by_user_id[r[1]] = Report(id=r[0], user_id=r[1], created_at=r[2])

        user_setting_by_user_id: Dict[str, UserSetting] = {}
        for r in user_setting_rows:
            user_setting_by_user_id[r[0]] = UserSetting(user_id=r[0], report_max_duration=r[1])

        for user_id, report in report_by_user_id.items():
            user_setting = user_setting_by_user_id.get(user_id)
            if user_setting and report.created_at + timedelta(seconds=user_setting.report_max_duration) <= datetime.now(
                    timezone.utc):
                # finalize the report
                with get_session(write=True) as session:
                    Report.update(session, report.id, status=ReportStatus.Finalized)
                    Report.add(session, report.user_id, {})
                    logger.info("report {} exceed max duration {} seconds, finalized at {}".format(
                        report.id,
                        user_setting.report_max_duration,
                        datetime.now(timezone.utc)
                    ))

        # check if we have more records to process
        has_db_records = len(report_rows) > 0
        offset += len(report_rows)


# TODO: not run by recurring, create a one-time eventbus schedule when a new report is created
if __name__ == '__main__':
    init_job()
    job_main()
