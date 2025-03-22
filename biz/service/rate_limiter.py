from flask import Flask, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

ip_limiter = Limiter(key_func=get_remote_address)


def get_user_id():
    return request.ctx.user_id


user_limiter = Limiter(key_func=get_user_id)
