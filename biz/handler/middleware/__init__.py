import os
import sys
import jwt
from functools import wraps
from flask import request
from pydantic import ValidationError
from biz.utils.env import RuntimeEnv
from biz.utils.response import HTTPResponse, SError, ResponseCode


class RequestContext:
    def __init__(self):
        self.user_id = None

def jwt_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        resp = HTTPResponse(request.path)
        token = request.cookies.get(RuntimeEnv.Instance().JWT_COOKIE_NAME)
        if not token:
            resp.set_error(ResponseCode.InvalidAuth.create_error('No token found'))
            return resp.return_with_log()

        try:
            payload = jwt.decode(token, RuntimeEnv.Instance().JWT_SECRET, algorithms=['HS256'])
            user_id = payload.get('id')
            if not user_id:
                resp.set_error(ResponseCode.InvalidAuth.create_error('Invalid token, unknown user_id'))
                return resp.return_with_log()

            # store user_id in request context
            if not request.ctx:
                request.ctx = RequestContext()
            request.ctx.user_id = user_id

            # execute next handler
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            resp.set_error(ResponseCode.InvalidAuth.create_error('Token has expired'))
            return resp.return_with_log()
        except jwt.InvalidTokenError:
            resp.set_error(ResponseCode.InvalidAuth.create_error('Invalid token'))
            return resp.return_with_log()

    return decorated_function

def validation_error_to_str(err: ValidationError):
    for e in err.errors():
        return f'{e.get("loc")[0]} {e.get("msg")} but {e.get("type")}'

def catch_error(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        resp = HTTPResponse(request.path)
        try:
            return f(*args, **kwargs)
        except SError as e:
            resp.set_error(e)
            return resp.return_with_log()
        except ValidationError as e:
            resp.set_error(ResponseCode.InvalidParam.create_error(validation_error_to_str(e)))
            return resp.return_with_log()
        except Exception as e:
            # TODO: catch other type of Exception like from db, s3, mq, etc.
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)
            print(exc_type, fname, exc_tb.tb_lineno)
            resp.set_error(ResponseCode.InternalUnknownError.create_error(str(e)))
            return resp.return_with_log()

    return decorated_function


__all__ = ['RequestContext', 'jwt_auth', 'catch_error']