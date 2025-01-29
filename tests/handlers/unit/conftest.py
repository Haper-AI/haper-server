import pytest
from pytest_postgresql import factories

from flask import Flask
from biz.utils.env import RuntimeEnv
from biz.handler import api_v1
from biz.service.db import init_db, get_engine
from biz.dal.base import Base

postgresql_noproc = factories.postgresql_noproc(
    user="root",
    host="localhost",
    password="123456",
    dbname="tests-haper-unit",
)
postgresql = factories.postgresql("postgresql_noproc")


@pytest.fixture()
def app(postgresql):
    RuntimeEnv.Instance().POSTGRES_DSN = f'postgresql+psycopg://{postgresql.info.user}:{postgresql.info.password}@{postgresql.info.host}:{postgresql.info.port}/{postgresql.info.dbname}'
    app = Flask(RuntimeEnv.Instance().APP_NAME)
    app.register_blueprint(api_v1)
    init_db()
    app.config.update({
        "TESTING": True,
    })

    # other setup can go here

    # create db tables
    Base.metadata.create_all(bind=get_engine())

    yield app

    # clean up / reset resources here


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def runner(app):
    return app.test_cli_runner()
