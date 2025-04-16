import base64
import hashlib
import hmac
import json
from typing import Dict, List

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers import modes, algorithms, Cipher
from cryptography.hazmat.primitives.padding import PKCS7
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from flask import request

from flask import Blueprint
from pydantic import BaseModel, EmailStr, field_validator

from biz.handler.middleware import catch_error
from biz.service.aws.sm import get_outlook_sub_private
from biz.utils.logger import logger
from biz.controller import message_sync as message_sync_ctrl

webhook_routes = Blueprint("webhooks", __name__, url_prefix="/webhook")


class GmailPubsubMessage(BaseModel):
    class _MessageData(BaseModel):
        emailAddress: EmailStr
        historyId: int

    data: _MessageData
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
    message_sync_ctrl.sync_user_gmail_message(str(req.data.emailAddress), req.data.historyId)
    return "success", 200

@webhook_routes.route("/outlook-sync", methods=["POST"])
@catch_error
def outlook_sync():
    args = request.args.to_dict()
    if "validationToken" in args:
        return args["validationToken"], 200
    value = request.get_json().get("value", [])
    logger.info("received outlook sync request: %s", value)
    message_ids_by_email: Dict[str, List[str]] = {}
    for v in value:
        encrypted_data_key = base64.b64decode(v["encryptedContent"]["dataKey"])
        private_key = serialization.load_pem_private_key(
            get_outlook_sub_private().encode('utf-8'),
            password=None,
            backend=default_backend()
        )
        data_key = private_key.decrypt(
            encrypted_data_key,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA1()),
                algorithm=hashes.SHA1(),
                label=None
            )
        )

        # verify data signature
        data_signature = base64.b64decode(v["encryptedContent"]["dataSignature"])
        data = base64.b64decode(v["encryptedContent"]["data"])
        computed_hmac = hmac.new(data_key, data, hashlib.sha256).digest()
        if not hmac.compare_digest(computed_hmac, data_signature):
            raise ValueError("Data signature verification failed. Possible tampering detected.")

        # do decrypt
        ## Extract IV (first 16 bytes of the symmetric key)
        iv = data_key[:16]

        ## Initialize AES cipher
        cipher = Cipher(
            algorithms.AES(data_key),
            modes.CBC(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()

        # Perform decryption
        decrypted_padded = decryptor.update(data) + decryptor.finalize()

        # Remove PKCS7 padding
        unpadder = PKCS7(128).unpadder()
        decrypted_data = unpadder.update(decrypted_padded) + unpadder.finalize()

        decrypted_json = json.loads(decrypted_data.decode("utf-8"))
        email = decrypted_json["toRecipients"][0]["emailAddress"]["address"]
        if email not in message_ids_by_email:
            message_ids_by_email[email] = []
        message_ids_by_email[email].append(v["resourceData"]["id"])

    message_sync_ctrl.sync_user_outlook_message(message_ids_by_email)
    return "success", 200


__all__ = ['webhook_routes']
