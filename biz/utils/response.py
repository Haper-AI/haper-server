import time
from enum import IntEnum
from flask import jsonify, make_response

from .env import RuntimeEnv
from .logger import logger


class ResponseCode(IntEnum):
    SUCCESS = 0
    InvalidParam = 1001
    InvalidAuth = 1101
    UserNoPermission = 1102
    InternalUnknownError = 9999

    def create_error(self, message: str = '') -> 'SError':
        return SError(self, message)


class SError(Exception):
    def __init__(self, code: ResponseCode, message: str = ''):
        super().__init__(message)
        self.code = code
        self.message = message


class HTTPResponse:

    def __init__(self, method: str, uri: str):
        self.cookie_response = make_response()
        self.http_status = 200  # the http status code
        self.status = ResponseCode.SUCCESS  # the internal service status code
        self.message = 'success'
        self.method = method
        self.uri = uri
        self.elapsed = 0
        self.time = int(time.time())
        self.data = None

    def set_data(self, data):
        self.data = data

    def set_error(self, err: SError):
        self.status = err.code
        self.message = err.message
        if self.status == ResponseCode.InvalidParam:
            self.http_status = 400
        elif self.status in [ResponseCode.InvalidAuth, ResponseCode.UserNoPermission]:
            self.http_status = 401
        elif self.status == ResponseCode.InternalUnknownError:
            self.http_status = 500

    def set_cookie(self, *args, **kwargs):
        self.cookie_response.set_cookie(*args, **kwargs)

    def set_jwt_auth_cookie(self, auth_token):
        self.set_cookie(
            RuntimeEnv.Instance().JWT_AUTH_COOKIE_NAME,
            auth_token,
            httponly=True,
            secure=False,
            samesite='Lax'
        )

    def return_with_log(self):
        if self.http_status == 200:
            logger.info('%s %s %d, elapsed: %dms', self.method, self.uri, self.http_status, self.elapsed)
        elif self.http_status in [400, 401]:
            logger.info('%s %s %d, elapsed: %dms, err=%s', self.method, self.uri, self.http_status, self.elapsed,
                        self.message)
        else:
            logger.error('%s %s %d, elapsed: %dms, err=%s', self.method, self.uri, self.http_status, self.elapsed,
                         self.message)

        response = jsonify({
            'status': self.status,
            'message': self.message,
            'uri': self.uri,
            'elapsed': int(time.time() - self.time),
            'data': self.data,
        })
        for cookie in self.cookie_response.headers.getlist("Set-Cookie"):
            response.headers.add("Set-Cookie", cookie)
        return response, self.http_status
