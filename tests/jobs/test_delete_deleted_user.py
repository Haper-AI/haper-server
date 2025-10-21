from datetime import datetime, timezone, timedelta

from app.jobs.delete_marked_deleted_user import init_job, job_main
from biz.dal.user import User
from biz.service.db import get_session
from tests import generate_random_gmail


def test_delete_marked_deleted_user():
    with get_session(write=True) as session:
        # Create a user with deleted_at set to 31 days ago
        user = User.add(session, "user name", generate_random_gmail(8), email_verified=True)
        user.deleted_at = datetime.now(timezone.utc) - timedelta(days=31)
        user_id = user.id

    # Run the job
    init_job()
    job_main()

    # Check if the user was deleted
    with get_session(write=False) as session:
        deleted_user = User.get_by_id(session, user_id)

    assert deleted_user is None
