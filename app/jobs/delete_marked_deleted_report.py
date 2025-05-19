from datetime import timedelta, datetime, timezone

from biz.dal.report import Report
from biz.service.db import init_db, get_session
from biz.utils.logger import logger


def init_job():
    init_db()


def job_main():
    limit = 50
    offset = 0
    has_db_records = True
    while has_db_records:
        with get_session(write=False) as session:
            rows = session.query(Report.id, Report.deleted_at).filter(
                Report.deleted_at.isnot(None)
            ).offset(offset).limit(limit).all()

        reports = [Report(id=r[0], deleted_at=r[1]) for r in rows]
        for r in reports:
            if r.deleted_at + timedelta(days=30) <= datetime.now(timezone.utc):
                with get_session(write=True) as session:
                    Report.delete(session, r.id)
                    logger.info("report {} deleted at {}".format(
                        r.id,
                        datetime.now(timezone.utc)
                    ))

        # check if we have more records to process
        has_db_records = len(reports) > 0
        offset += len(reports)


def handler(event, context):
    init_job()
    job_main()
