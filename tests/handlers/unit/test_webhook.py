import base64
import hashlib
import hmac
import json
from datetime import timedelta, datetime

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.padding import PKCS7

from biz.dal.message_tracking import MessageTrackingRecord
from biz.dal.report import Report
from biz.service.db import get_session
from tests import generate_random_string, generate_random_gmail
from unittest.mock import patch, MagicMock

from tests.handlers.unit.conftest import create_rsa_pairs


class TestGmailSyncWebhook:
    @patch('biz.controller.message_sync.build_gmail_client')
    def test_success(self, mock_build_gmail_client, client, new_user_gmail_account):
        user, account = new_user_gmail_account
        with get_session(write=True) as session:
            MessageTrackingRecord.add(session, user.id, account.id, extra_info={
                "pre_history_id": "some_history_id",
            })
            Report.add(session, user.id, {})

        # configure mock gmail client api
        mock_gmail_client = MagicMock()
        mock_gmail_client.users().history().list.return_value.execute.return_value = {
            'history': [
                {
                    'messagesAdded': [
                        {
                            'message': {
                                'id': 'test_message_id',
                                'threadId': 'test_message_id',
                            }
                        }
                    ]
                }
            ]
        }
        mock_credential = MagicMock()
        mock_credential.token = generate_random_string(10)
        mock_credential.expiry = datetime.now() + timedelta(hours=2)

        mock_build_gmail_client.return_value = (mock_gmail_client, mock_credential)

        response = client.post('/api/v1/webhook/gmail-sync', json={
            'message': {
                'data': base64.b64encode(json.dumps({
                    'emailAddress': account.email,
                    'historyId': 10,
                }).encode('utf-8')).decode(),
                'message_id': "test_message_id",
                'publish_time': "test_publish_time",
            }
        })

        assert response.status_code == 200

    class TestFail:
        def test_fail_by_no_registered_email(self, client):
            email = generate_random_gmail(8)
            response = client.post('/api/v1/webhook/gmail-sync', json={
                'message': {
                    'data': base64.b64encode(json.dumps({
                        'emailAddress': email,
                        'historyId': 10,
                    }).encode('utf-8')).decode(),
                    'message_id': "test_message_id",
                    'publish_time': "test_publish_time",
                }
            })
            assert response.status_code == 200


class TestOutlookSyncWebhook:
    class TestSuccess:
        def test_success_with_validation_token(self, client):
            response = client.post('/api/v1/webhook/outlook-sync?validationToken=someToken')
            assert response.status_code == 200

        def test_success_with_data(self, client, new_user_outlook_account):
            user, account = new_user_outlook_account
            with get_session(write=True) as session:
                MessageTrackingRecord.add(session, user.id, account.id)
                Report.add(session, user.id, {})

            private_key_str, public_key_str = create_rsa_pairs()

            public_key = serialization.load_pem_public_key(
                public_key_str.encode('utf-8')
            )

            data_key_bytes = AESGCM.generate_key(bit_length=256)  # Generate a 256-bit AES key
            # encrypt data key using public key
            encrypted_data_key = public_key.encrypt(data_key_bytes, asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA1()),
                algorithm=hashes.SHA1(),
                label=None
            ))

            data_json = {
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": user.email,
                        }
                    }
                ]
            }
            data_json_bytes = json.dumps(data_json).encode('utf-8')

            # encrypt data using data key
            iv = data_key_bytes[:16]
            cipher = Cipher(
                algorithms.AES(data_key_bytes),
                modes.CBC(iv),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            padder = PKCS7(128).padder()
            padded_data_json_bytes = padder.update(data_json_bytes) + padder.finalize()

            ## preform encryption
            encrypted_data = encryptor.update(padded_data_json_bytes) + encryptor.finalize()

            # do signature for encrypted data
            signature = hmac.new(data_key_bytes, encrypted_data, hashlib.sha256).digest()

            with patch('biz.handler.webhook.get_outlook_sub_private', return_value=private_key_str):
                response = client.post('/api/v1/webhook/outlook-sync', json={
                    "value": [
                        {
                            "resourceData": {
                                "id": "some_id",
                            },
                            "encryptedContent": {
                                "data": base64.b64encode(encrypted_data).decode(),
                                "dataKey": base64.b64encode(encrypted_data_key).decode(),
                                "dataSignature": base64.b64encode(signature).decode(),
                            }
                        }
                    ]
                })

                assert response.status_code == 200

    class TestFail:
        def test_fail_by_no_registered_email(self, client):
            email = generate_random_gmail(8)
            response = client.post('/api/v1/webhook/gmail-sync', json={
                'message': {
                    'data': base64.b64encode(json.dumps({
                        'emailAddress': email,
                        'historyId': 10,
                    }).encode('utf-8')).decode(),
                    'message_id': "test_message_id",
                    'publish_time': "test_publish_time",
                }
            })
            assert response.status_code == 200
