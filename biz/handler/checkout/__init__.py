from typing import Literal

from flask import Blueprint, request
from pydantic import BaseModel

from biz.handler.middleware import catch_error, user_auth
from biz.service.stripe import stripe
from biz.utils.response import HTTPResponse
from biz.controller import user_subscription as user_subscription_ctrl

checkout_routes = Blueprint('checkout_routes', __name__, url_prefix='/checkout')


class NewCheckoutSessionReq(BaseModel):
    return_url: str
    billing_cycle: Literal['month']


@checkout_routes.route('/session', methods=['POST'])
@catch_error
@user_auth()
def new_checkout_session():
    resp = HTTPResponse(request.method, request.path)
    req = NewCheckoutSessionReq(**request.get_json())

    session_id, client_secret = user_subscription_ctrl.new_checkout_session(
        request.ctx.user_id,
        request.ctx.user_email,
        request.ctx.stripe_customer_id,
        req.return_url,
        req.billing_cycle
    )

    resp.set_data({
        'checkout_session_id': session_id,
        'checkout_session_client_secret': client_secret
    })

    return resp.return_with_log()


class GetCheckoutSessionStatusReq(BaseModel):
    session_id: str


@checkout_routes.route('/session-status')
@catch_error
@user_auth()
def get_checkout_session_status():
    resp = HTTPResponse(request.method, request.path)
    req = GetCheckoutSessionStatusReq(**request.args.to_dict())
    checkout_session = stripe.checkout.Session.retrieve(req.session_id)
    # TODO: decide whether to check the email
    # if request.ctx.user_email != checkout_session.customer_details.email:
    #     raise
    resp.set_data({
        "checkout_status": checkout_session.status,
        "customer_email": checkout_session.customer_details.email,
    })
    return resp.return_with_log()
