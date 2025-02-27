from flask import Blueprint, request

from biz.handler.middleware import catch_error
from biz.utils.response import HTTPResponse
from biz.controller import system_preset as system_preset_ctrl

system_routes = Blueprint('system_routes', __name__, url_prefix='/system')


@system_routes.route('/message_tags')
@catch_error
def list_message_tags():
    resp = HTTPResponse(request.method, request.path)
    message_tags = system_preset_ctrl.list_message_tags()
    resp.set_data({
        'message_tags': message_tags
    })
    return resp.return_with_log()
