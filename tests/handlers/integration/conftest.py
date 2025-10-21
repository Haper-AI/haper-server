from tests.handlers.conf_factory import new_handler_test_conf

app, client, runner = new_handler_test_conf(
    scope="module",
    db_name="tests-haper-api-integration",
    sqs_queue_name="test-integration-async-action",
)