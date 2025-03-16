from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

ip_limiter = None

def init_ip_limiter(app: Flask):
    global limiter
    limiter = Limiter(
        get_remote_address,
        app=app,
    )

user_limiter = None
def init_user_limiter(app: Flask):
    global limiter
    limiter = Limiter(
        get_remote_address, # TODO: change to user id func
        app=app,
    )