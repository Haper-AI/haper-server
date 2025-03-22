import pytest
from pytest_postgresql.janitor import DatabaseJanitor
from sqlalchemy import text

from biz.dal.base import Base
from biz.service.db import init_db, get_engine, get_session
from biz.utils.env import RuntimeEnv


@pytest.fixture(scope="module", autouse=True)
def conf_db():
    user = "root"
    password = "123456"
    host = "localhost"
    port = 5432
    db_name = "test-consumer"
    janitor = DatabaseJanitor(
        user=user,
        password=password,
        host=host,
        port=port,
        dbname=db_name,
        version="10.1",
    )

    janitor.init()

    RuntimeEnv.Instance().POSTGRES_DSN = f'postgresql+psycopg://{user}:{password}@{host}:{port}/{db_name}'
    init_db()

    # add pgvector extension
    with get_session(write=True) as session:
        session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    # create db tables
    Base.metadata.create_all(bind=get_engine())

    yield janitor

    janitor.drop()


