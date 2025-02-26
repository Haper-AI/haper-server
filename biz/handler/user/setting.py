from flask import request

from .routes import user_routes
from biz.handler.middleware import catch_error, jwt_auth
from biz.utils.response import HTTPResponse
from biz.controller.user import get_user_info


@user_routes.route('/info')
@catch_error
@jwt_auth
def user_info():
    resp = HTTPResponse(request.method, request.path)

    user = get_user_info(request.ctx.user_id)
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
