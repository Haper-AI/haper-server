import datetime
from functools import wraps
from typing import Optional

import jwt
from flask import request
from flask_limiter import RateLimitExceeded
from pydantic import ValidationError
from werkzeug.exceptions import UnsupportedMediaType

from biz.dal.user import User
from biz.dal.user_subscription import UserSubscription, UserSubscriptionStatus
from biz.service.db import get_session
from biz.utils import track_haper_error
from biz.utils.env import RuntimeEnv
from biz.utils.logger import logger
from biz.utils.response import HTTPResponse, SError, ResponseCode


class RequestContext:
    def __init__(self):
        self.user_id: Optional[str] = None
        self.user_email: Optional[str] = None
        self.stripe_customer_id: Optional[str] = None


USER_JWT_AUTH_VALID_PERIOD = datetime.timedelta(days=30)


def gen_jwt_auth(user_id: str) -> str:
    payload = {
        'id': user_id,
        'exp': datetime.datetime.now(datetime.timezone.utc) + USER_JWT_AUTH_VALID_PERIOD,
        'iat': datetime.datetime.now(datetime.timezone.utc)
    }
    return jwt.encode(payload, RuntimeEnv.Instance().JWT_AUTH_SECRET, algorithm='HS256')


def user_auth(check_subscription: bool = False):
    """
    A decorator for user authentication.

    This function wraps the provided handler function to ensure that a valid
    JWT token is present in the request cookies and check for some other auths.
    If authentication is successful, it stores the user_id from the token in the request.ctx,
    a {RequestContext} object for further use.

    Arguments:
        :param check_subscription: whether to check the user's subscription is active.

    Returns:
        function: The decorated function with JWT authentication logic.
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            resp = HTTPResponse(request.method, request.path)
            token = request.cookies.get(RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME)
            if not token:
                resp.set_error(ResponseCode.InvalidAuth.create_error('No user token found'))
                return resp.return_with_log()

            try:
                payload = jwt.decode(token, RuntimeEnv.Instance().JWT_AUTH_SECRET, algorithms=['HS256'])
                user_id = payload.get('id')
                if not user_id:
                    resp.set_error(ResponseCode.InvalidAuth.create_error('Invalid token, unknown user_id'))
                    return resp.return_with_log()

                with get_session(write=False) as session:
                    # get user
                    user = User.get_by_id(session, user_id)
                    if not user or user.deleted_at:
                        resp.set_error(ResponseCode.UnsupportedAction.create_error("user does not exist"))
                        return resp.return_with_log()

                    # check subscription if is needed
                    if check_subscription:
                        user_subscription = UserSubscription.get_by_user_id(session, user.id)
                        if not user_subscription or user_subscription.subscription_status not in [
                            UserSubscriptionStatus.Active, UserSubscriptionStatus.Trialing]:
                            resp.set_error(
                                ResponseCode.UnsupportedAction.create_error("user subscription is not active"))
                            return resp.return_with_log()

                # store user_id in request context
                if not hasattr(request, 'ctx'):
                    setattr(request, 'ctx', RequestContext())
                request.ctx.user_id = user_id
                request.ctx.user_email = user.email
                request.ctx.stripe_customer_id = user.stripe_customer_id

                # execute next handler
                return f(*args, **kwargs)
            except jwt.ExpiredSignatureError:
                resp.set_error(ResponseCode.InvalidAuth.create_error('Token has expired'))
                return resp.return_with_log()
            except jwt.InvalidTokenError:
                resp.set_error(ResponseCode.InvalidAuth.create_error('Invalid token'))
                return resp.return_with_log()

        return decorated_function

    return decorator


def validation_error_to_str(err: ValidationError):
    errors = err.errors()
    if len(errors) > 0:
        e = errors[0]
        if e.get('loc'):
            return f'{e.get("loc")[0]} {e.get("msg")}'
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
        resp = HTTPResponse(request.method, request.path)
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
        except RateLimitExceeded:
            resp.set_error(ResponseCode.UnsupportedAction.create_error("too many requests"))
            return resp.return_with_log()
        except Exception as e:
            # TODO: catch other type of Exception like from db, s3, mq, etc.
            file_name, line_number, func_name, text = track_haper_error(e)
            logger.error(f"Error in {file_name}:{line_number}, in {func_name}: {text}")
            resp.set_error(ResponseCode.InternalUnknownError.create_error(str(e)))
            return resp.return_with_log()

    return decorated_function


__all__ = ['RequestContext', 'gen_jwt_auth', 'user_auth', 'catch_error']
