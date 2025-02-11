from tests.handlers.conf_factory import new_handler_test_conf

app, client, runner = new_handler_test_conf(scope="package", db_name="tests-haper-unit")
