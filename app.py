from flask import Flask
from biz.utils.env import RuntimeEnv
from biz.handler import api_v1
from biz.service.db import init_db


def create_app():
    app = Flask(RuntimeEnv.Instance().APP_NAME)
    app.register_blueprint(api_v1)
    init_db()
    return app

app = create_app()

@app.route("/ping")
def ping():
    return "pong"


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8888)
