from flask import Blueprint
from .user import user_routes
from .webhook import webhook_routes
api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")

api_v1.register_blueprint(user_routes)

api_v1.register_blueprint(webhook_routes)

__all__ = ["api_v1"]