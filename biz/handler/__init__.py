from flask import Blueprint

from .reports import report_routes
from .system import system_routes
from .user import user_routes
from .webhook import webhook_routes
from .messages import message_routes
from .checkout import checkout_routes

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")

api_v1.register_blueprint(user_routes)

api_v1.register_blueprint(webhook_routes)

api_v1.register_blueprint(message_routes)

api_v1.register_blueprint(system_routes)

api_v1.register_blueprint(report_routes)

api_v1.register_blueprint(checkout_routes)

__all__ = ["api_v1"]
