from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from biz.utils.env import RuntimeEnv

_engine: Engine
_session_factory: sessionmaker


def init_db():
    global _engine, _session_factory
    _engine = create_engine(RuntimeEnv.Instance().POSTGRES_DSN)
    _session_factory = sessionmaker(bind=_engine)


def init_db_with_engine(engine: Engine):
    global _engine, _session_factory
    _engine = engine
    _session_factory = sessionmaker(bind=_engine)


def get_engine():
    return _engine


# Define a context manager for session management
@contextmanager
def get_session(write: bool = False):
    session = _session_factory()  # Create a session
    try:
        yield session  # Yield the session for use
    except Exception as e:
        if write:
            session.rollback()
        raise e
    finally:
        if write:
            session.commit()
        session.close()  # Close the session after use
