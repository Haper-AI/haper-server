from flask import Flask
from biz.utils.env import RuntimeEnv
from biz.handler import api_v1
app = Flask(RuntimeEnv.Instance().APP_NAME)

app.register_blueprint(api_v1)

@app.route("/ping")
def ping():
    return "pong"

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8888)