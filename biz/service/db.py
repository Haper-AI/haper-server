from typing import Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from biz.utils.env import RuntimeEnv

_engine: Engine
_session_factory: sessionmaker


def init_db():
    global _engine, _session_factory
    # use pool_pre_ping right now to prevent TCP EOF as the server and db cluster may distribute in different data center
    # learn more in this post: https://blog.stigok.com/2021/02/28/sqlalchemy-postgres-ssl-eof-detected.html
    _engine = create_engine(RuntimeEnv.Instance().POSTGRES_DSN, pool_pre_ping=True)
    _session_factory = sessionmaker(bind=_engine)


def get_engine():
    return _engine


# Define a context manager for session management
@contextmanager
def get_session(write: bool = False):
    session = _session_factory()  # Create a session
    if write:
        session.begin()
    try:
        yield session  # Yield the session for use
        if write:
            session.commit()
        session.close()  # Close the session after use
    except Exception as e:
        session.rollback()
        session.close()
        raise e
