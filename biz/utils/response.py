import time
from enum import IntEnum
from flask import jsonify
import logging
from .env import RuntimeEnv

logger = logging.getLogger(RuntimeEnv.Instance().APP_NAME)


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

    def __init__(self, uri: str = ''):
        self.http_status = 200  # the http status code
        self.status = ResponseCode.SUCCESS  # the internal service status code
        self.message = 'success'
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

    def return_with_log(self):
        if self.http_status == 200:
            logger.info('%s %d, elapsed: %dms', self.uri, self.http_status, self.elapsed)
        elif self.http_status in [400, 401]:
            logger.info('%s %d, elapsed: %dms, err=%s', self.uri, self.http_status, self.elapsed, self.message)
        else:
            logger.error('%s %d, elapsed: %dms, err=%s', self.uri, self.http_status, self.elapsed, self.message)

        return jsonify({
            'status': self.status,
            'message': self.message,
            'uri': self.uri,
            'elapsed': int(time.time() - self.time),
            'data': self.data,
        }), self.http_status
