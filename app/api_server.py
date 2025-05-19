from flask import Flask
from flask_cors import CORS
from flask.logging import default_handler

from biz.service.aws.sm import load_secret
from biz.service.rate_limiter import user_limiter
from biz.service.aws.sqs import init_sqs
from biz.utils.env import RuntimeEnv
from biz.handler import api_v1
from biz.service.db import init_db


def create_app():
    app = Flask(RuntimeEnv.Instance().APP_NAME)

    app.register_blueprint(api_v1)
    init_db()
    init_sqs()
    load_secret()
    user_limiter.init_app(app)

    CORS(app, resources={
        r"/*": {
            "origins": RuntimeEnv.Instance().ALLOW_ORIGINS,
            "supports_credentials": True,
        }
    })
    app.logger.removeHandler(default_handler)
    return app


app = create_app()


@app.route("/ping")
def ping():
    return "pong"


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8888)
