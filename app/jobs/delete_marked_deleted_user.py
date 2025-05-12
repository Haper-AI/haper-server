from datetime import timedelta, datetime, timezone

from biz.dal.user import User
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
            user = session.query(User).filter(
                User.deleted_at.isnot(None)
            ).offset(offset).limit(limit).all()

        for u in user:
            if u.deleted_at + timedelta(days=30) <= datetime.now(timezone.utc):
                with get_session(write=True) as session:
                    User.delete(session, u.id)
                    logger.info("user {} deleted at {}".format(
                        u.id,
                        datetime.now(timezone.utc)
                    ))

        # check if we have more records to process
        has_db_records = len(user) > 0
        offset += len(user)


def handler(event, context):
    init_job()
    job_main()
