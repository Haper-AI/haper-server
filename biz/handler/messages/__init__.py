from flask import Blueprint
from .tracking import tracking_routes

message_routes = Blueprint("message_related_api", __name__, url_prefix="/message")

message_routes.register_blueprint(tracking_routes)

__all__ = ['message_routes']