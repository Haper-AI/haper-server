from typing import List
from flask import request
from pydantic import BaseModel

from .routes import user_routes
from biz.handler.middleware import catch_error, jwt_auth
from biz.utils.response import HTTPResponse
from biz.controller import user as user_ctrl
from biz.controller import user_setting as user_setting_ctrl

@user_routes.route('/info')
@catch_error
@jwt_auth
def get_user_info():
    resp = HTTPResponse(request.method, request.path)

    user = user_ctrl.get_user_info(request.ctx.user_id)
    resp.set_data({
        'user': {
            'id': user.id,
            'name': user.name,
            'image': user.image,
            'email': user.email,
            'email_verified': user.email_verified,
            'created_at': user.created_at,
        }
    })
    return resp.return_with_log()


@user_routes.route('/setting')
@catch_error
@jwt_auth
def get_user_setting():
    resp = HTTPResponse(request.method, request.path)
    user_setting = user_setting_ctrl.get_user_setting(request.ctx.user_id)
    resp.set_data({
        "setting": {
            "key_message_tags": user_setting.key_message_tags,
        },
    })
    return resp.return_with_log()

class CreateUpdateUserSettingReq(BaseModel):
    key_message_tags: List[str]

@user_routes.route('/setting', methods=['POST'])
@catch_error
@jwt_auth
def new_user_setting():
    resp = HTTPResponse(request.method, request.path)
    req = CreateUpdateUserSettingReq(**request.get_json())
    user_setting = user_setting_ctrl.new_user_setting(request.ctx.user_id, req.key_message_tags)
    resp.set_data({
        "setting": {
            "key_message_tags": user_setting.key_message_tags,
        },
    })
    return resp.return_with_log()


@user_routes.route('/setting', methods=['PUT'])
@catch_error
@jwt_auth
def update_user_setting():
    resp = HTTPResponse(request.method, request.path)
    req = CreateUpdateUserSettingReq(**request.get_json())
    user_setting = user_setting_ctrl.update_user_setting(request.ctx.user_id, req.key_message_tags)
    resp.set_data({
        "setting": {
            "key_message_tags": user_setting.key_message_tags,
        },
    })
    return resp.return_with_log()
