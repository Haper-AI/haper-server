from flask import Flask
from biz.utils.env import RuntimeEnv
from biz.handler import api_v1
from biz.service import init_dependent_services

app = Flask(RuntimeEnv.Instance().APP_NAME)


@app.route("/ping")
def ping():
    return "pong"


if __name__ == "__main__":
    app.register_blueprint(api_v1)
    init_dependent_services()
    app.run(debug=True, host="0.0.0.0", port=8888)
