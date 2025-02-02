import traceback
from functools import wraps
from typing import Optional

import jwt
from flask import request
from pydantic import ValidationError
from werkzeug.exceptions import UnsupportedMediaType

from biz.utils.env import RuntimeEnv
from biz.utils.logger import logger
from biz.utils.response import HTTPResponse, SError, ResponseCode


class RequestContext:
    def __init__(self):
        self.user_id: Optional[str] = None


def jwt_auth(f):
    """
    A decorator for JWT-based authentication.

    This function wraps the provided handler function to ensure that a valid
    JWT token is present in the request cookies. If authentication is successful, 
    it stores the user_id from the token in the request.ctx, a {RequestContext} object
    for further use.

    Arguments:
        f (function): The flask handler function to be decorated.

    Returns:
        function: The decorated function with JWT authentication logic.
    """

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
    errors = err.errors()
    if len(errors) > 0:
        e = errors[0]
        if e.get('loc'):
            return f'{e.get("loc")[0]} {e.get("msg")} but {e.get("type")}'
        elif e.get('ctx'):
            return str(e.get("ctx").get("error"))
    return 'Unknown Validation Error'


def catch_error(f):
    """
    A decorator to handle exceptions and format responses.

    This function wraps the provided handler function to catch and handle known 
    and unknown exceptions during its execution. It ensures that meaningful and
    structured error responses are returned to the client.

    Arguments:
        f (function): The flask handler function to be decorated.

    Returns:
        function: The decorated function with error handling logic.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        resp = HTTPResponse(request.path)
        try:
            return f(*args, **kwargs)
        except SError as e:
            resp.set_error(e)
            return resp.return_with_log()
        except UnsupportedMediaType as e:
            resp.set_error(ResponseCode.InvalidParam.create_error(str(e)))
            return resp.return_with_log()
        except ValidationError as e:
            # Handle pydantic validation errors and return appropriate response
            resp.set_error(ResponseCode.InvalidParam.create_error(validation_error_to_str(e)))
            return resp.return_with_log()
        except Exception as e:
            # TODO: catch other type of Exception like from db, s3, mq, etc.
            tb = traceback.extract_tb(e.__traceback__)
            file_name, line_number, func_name, text = tb[-1]  # Get the last (most recent) traceback entry
            logger.error(f"Error in {file_name}, line {line_number}, in {func_name}: {text}")
            resp.set_error(ResponseCode.InternalUnknownError.create_error(str(e)))
            return resp.return_with_log()

    return decorated_function


__all__ = ['RequestContext', 'jwt_auth', 'catch_error']
