import pytest
from pytest_postgresql.janitor import DatabaseJanitor
from flask import Flask

from biz.service.sqs import init_sqs, get_sqs_client
from biz.utils.env import RuntimeEnv
from biz.handler import api_v1
from biz.service.db import init_db, get_engine
from biz.dal.base import Base


def new_handler_test_conf(scope, db_name: str, sqs_queue_name: str):
    @pytest.fixture(scope=scope)
    def app():
        # set up db
        user = "root"
        password = "123456"
        host = "localhost"
        port = 5432
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
        app = Flask(RuntimeEnv.Instance().APP_NAME)
        app.register_blueprint(api_v1)
        init_db()
        app.config.update({
            "TESTING": True,
        })

        # create db tables
        Base.metadata.create_all(bind=get_engine())

        # set up sqs
        init_sqs()
        RuntimeEnv.Instance().SQS_REPORT_UPDATE_QUEUE_URL = get_sqs_client(). \
            create_queue(QueueName=sqs_queue_name)["QueueUrl"]

        # other setup can go here

        yield app

        # clean up / reset resources here
        janitor.drop()
        get_sqs_client().delete_queue(QueueUrl=RuntimeEnv.Instance().SQS_REPORT_UPDATE_QUEUE_URL)

    @pytest.fixture(scope=scope)
    def client(app):
        return app.test_client()

    @pytest.fixture(scope=scope)
    def runner(app):
        return app.test_cli_runner()

    return app, client, runner
