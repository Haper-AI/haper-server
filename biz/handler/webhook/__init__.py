import base64
import json

from flask import request

from flask import Blueprint
from pydantic import BaseModel, EmailStr, field_validator

from biz.handler.middleware import catch_error
from biz.utils.logger import logger
from biz.controller.message_sync import sync_user_gmail_message


webhook_routes = Blueprint("message_delegation_api", __name__, url_prefix="/webhook")

class GmailPubsubMessage(BaseModel):
    class MessageData(BaseModel):
        emailAddress: EmailStr
        historyId: int

    data: MessageData
    message_id: str
    publish_time: str

    @field_validator("data", mode="before")
    @classmethod
    def decode_base64_address(cls, value):
        if isinstance(value, str):
            decoded_json = base64.b64decode(value).decode("utf-8")
            return json.loads(decoded_json)
        return value

@webhook_routes.route("/gmail-sync", methods=["POST"])
@catch_error
def user_gmail_sync():
    """
    The webhook endpoint for gmail sync pub/sub, see more in
    https://developers.google.com/gmail/api/guides/push
    """
    logger.info("received gmail sync request: %s", request.get_json())
    req = GmailPubsubMessage(**(request.get_json().get("message", {})))
    sync_user_gmail_message(str(req.data.emailAddress), req.data.historyId)
    return "success", 200


__all__ = ['webhook_routes']