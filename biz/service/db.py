from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from biz.utils.env import RuntimeEnv

engine = create_engine(RuntimeEnv.Instance().POSTGRES_DSN)
session_factory = sessionmaker(bind=engine)


def get_session():
    return session_factory()
