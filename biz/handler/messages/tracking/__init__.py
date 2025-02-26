from typing import Optional

from flask import Blueprint, request
from pydantic import BaseModel, PositiveInt, model_validator

from biz.controller.messag_tracking import get_user_all_message_tracking_status, \
    start_message_tracking_with_existing_account, start_message_tracking_with_new_account, end_message_tracking
from biz.handler.middleware import catch_error, jwt_auth
from biz.utils.response import HTTPResponse

tracking_routes = Blueprint("message_tracking_api", __name__, url_prefix="/tracking")

@tracking_routes.route("/status")
@catch_error
@jwt_auth
def list_message_tracking_status():
    resp = HTTPResponse(request.method, request.path)
    status = get_user_all_message_tracking_status(request.ctx.user_id)
    resp.set_data({
        "tracking_status": status
    })
    return resp.return_with_log()


class StartMessageTrackingReq(BaseModel):
    class _Account(BaseModel):
        provider: str
        provider_account_id: str
        access_token: str
        refresh_token: Optional[str] = None
        expires_at: Optional[PositiveInt] = None
        email: Optional[str] = None

    account_id: Optional[str] = None
    account: Optional[_Account] = None

    @model_validator(mode='after')
    def validate_req(self):
        if self.account is None and self.account_id is None:
            raise ValueError("account_id and account_info must provide one")

        return self


@tracking_routes.route("/start", methods=["POST"])
@catch_error
@jwt_auth
def start_message_tracking():
    resp = HTTPResponse(request.method, request.path)
    req = StartMessageTrackingReq(**request.get_json())
    if req.account_id:
        record = start_message_tracking_with_existing_account(request.ctx.user_id, req.account_id)
    else:
        record = start_message_tracking_with_new_account(
            request.ctx.user_id,
            req.account.provider,
            req.account.provider_account_id,
            req.account.access_token,
            req.account.refresh_token,
            req.account.expires_at,
            req.account.email,
        )
    resp.set_data({
        "new_tracking_status": record
    })
    return resp.return_with_log()


class EndMessageTrackingReq(BaseModel):
    account_id: str


@tracking_routes.route("/stop", methods=["POST"])
@catch_error
@jwt_auth
def stop_message_tracking():
    resp = HTTPResponse(request.method, request.path)
    req = EndMessageTrackingReq(**request.get_json())
    record = end_message_tracking(request.ctx.user_id, req.account_id)
    resp.set_data({
        "new_tracking_status": record
    })
    return resp.return_with_log()
