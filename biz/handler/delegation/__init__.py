from flask import Blueprint
from biz.handler.middleware import jwt_auth, catch_error

delegation_routes = Blueprint("message_delegation_api", __name__, url_prefix="/delegation")


@delegation_routes.route("/status")
@catch_error
@jwt_auth
def get_delegation_statistic():
    """
    Get available message delegation sources, and the delegation status of current user
    """
    raise NotImplemented


@delegation_routes.route("/<string:delegation_source>/start", methods=["POST"])
@catch_error
@jwt_auth
def start_delegation(delegation_source):
    raise NotImplemented


@delegation_routes.route("/<string:delegation_source>/stop", methods=["POST"])
@catch_error
@jwt_auth
def stop_delegation(delegation_source):
    raise NotImplemented


__all__ = ['delegation_routes']