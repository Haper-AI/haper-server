import base64
import hashlib
import hmac
import json
from datetime import timedelta, datetime, timezone

import pytest
import stripe
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.padding import PKCS7

from biz.controller.gmail_util import GmailAPIClient
from biz.controller.outlook_util import OutlookAPIClient
from biz.dal.message_tracking import MessageTrackingRecord
from biz.dal.report import Report, ReportType
from biz.dal.user import User
from biz.dal.user_subscription import UserSubscription, UserSubscriptionStatus
from biz.handler.middleware import gen_jwt_auth
from biz.service.db import get_session
from biz.utils.env import RuntimeEnv
from tests import generate_random_string, generate_random_gmail
from unittest.mock import patch, MagicMock, PropertyMock

from tests.handlers.unit.conftest import create_rsa_pairs


@pytest.fixture(scope="module")
def patch_gmail_api():
    # configure mock gmail client api
    mock_gmail_client = MagicMock()
    mock_gmail_client.users().history().list.return_value.execute.return_value = {
        'history': [
            {
                'id': "2",
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
    mock_gmail_client.users().watch.return_value.execute.return_value = {
        'historyId': 10,
        'expiration': (datetime.now() + timedelta(days=7)).timestamp() * 1000,
    }
    mock_credential = MagicMock()
    mock_credential.token = generate_random_string(10)
    mock_credential.expiry = datetime.now() + timedelta(hours=2)

    with patch.object(GmailAPIClient, "client", create=True, new_callable=PropertyMock) as p1:
        with patch.object(GmailAPIClient, "credential", create=True, new_callable=PropertyMock) as p2:
            p1.return_value = mock_gmail_client
            p2.return_value = mock_credential
            yield p1, p2


class TestGmailSyncWebhook:
    @pytest.mark.usefixtures("patch_gmail_api")
    def test_success(self, client, new_user_gmail_account):
        user, account = new_user_gmail_account
        with get_session(write=True) as session:
            MessageTrackingRecord.add(session, user.id, account.id, account.provider, extra_info={
                "pre_history_id": "some_history_id",
                "expiration": int((datetime.now() + timedelta(hours=12)).timestamp()),
            })
            Report.add(session, user.id, ReportType.Realtime, {})

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


@pytest.fixture(scope="module")
def patch_outlook_api():
    # configure mock gmail client api

    async def outlook_subscription_patch_mock(*args):
        return None

    mock_outlook_client = MagicMock()
    mock_outlook_client.subscriptions.by_subscription_id.return_value.patch = outlook_subscription_patch_mock
    mock_credential = MagicMock()
    mock_credential.access_token = generate_random_string(10)
    mock_credential.refresh_token = generate_random_string(10)
    mock_credential.expires_at = int((datetime.now() + timedelta(hours=2)).timestamp())

    with patch.object(OutlookAPIClient, "client", create=True, new_callable=PropertyMock) as p1:
        with patch.object(OutlookAPIClient, "credential", create=True, new_callable=PropertyMock) as p2:
            p1.return_value = mock_outlook_client
            p2.return_value = mock_credential
            yield p1, p2


class TestOutlookSyncWebhook:
    class TestSuccess:
        def test_success_with_validation_token(self, client):
            response = client.post('/api/v1/webhook/outlook-sync?validationToken=someToken')
            assert response.status_code == 200

        @pytest.mark.usefixtures("patch_outlook_api")
        def test_success_with_data(self, client, new_user_outlook_account):
            user, account = new_user_outlook_account
            with get_session(write=True) as session:
                MessageTrackingRecord.add(session, user.id, account.id, account.provider, extra_info={
                    "subscription_id": "some_subscription_id",
                    "expiration": int((datetime.now() + timedelta(hours=12)).timestamp()),
                })
                Report.add(session, user.id, ReportType.Realtime, {})

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
        def test_fail_by_not_registered_email(self, client):
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


class TestStripeEventWebhook:
    class TestSuccess:
        def test_customer_subscription_created(self, client, new_user):
            # Mock the Stripe API response
            event = {
                "type": "customer.subscription.created",
                "data": {
                    "object": {
                        "id": "sub_test_123",
                        "customer": "cus_test_123",
                        "status": "active",
                        "trial_end": int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp()),
                        "items": {
                            "object": "list",
                            "data": [
                                {
                                    "id": "si_test_123",
                                    "plan": {
                                        "id": "plan_test_123",
                                        "interval": "month",
                                    }
                                }
                            ]
                        }
                    }
                }
            }
            stripe.Webhook.construct_event = MagicMock(return_value=event)
            stripe.Customer.retrieve = MagicMock(return_value={
                "email": new_user.email,
            })

            # Simulate a request to the checkout session endpoint
            response = client.post('/api/v1/webhook/stripe-event', json=event, headers={
                "Stripe-Signature": "t=1234567890,v1=1234567890,v0=1234567890"
            })

            # Assert the response
            assert response.status_code == 200

        def test_customer_subscription_paused(self, client, new_user):
            customer_id = "cus_test_123"
            subscription_id = "sub_test_123"
            with get_session(write=True) as session:
                User.update(session, new_user.id, stripe_customer_id=customer_id)
                UserSubscription.add(session, new_user.id, customer_id, subscription_id, "month",
                                     UserSubscriptionStatus.Active)

            # Mock the Stripe API response
            event = {
                "type": "customer.subscription.paused",
                "data": {
                    "object": {
                        "id": subscription_id,
                        "customer": customer_id,
                        "status": "paused",
                    }
                }
            }
            stripe.Webhook.construct_event = MagicMock(return_value=event)

            # Simulate a request to the checkout session endpoint
            response = client.post('/api/v1/webhook/stripe-event', json=event, headers={
                "Stripe-Signature": "t=1234567890,v1=1234567890,v0=1234567890"
            })

            # Assert the response
            assert response.status_code == 200

        def test_customer_subscription_resumed(self, client, new_user):
            customer_id = "cus_test_123"
            subscription_id = "sub_test_123"
            with get_session(write=True) as session:
                User.update(session, new_user.id, stripe_customer_id=customer_id)
                UserSubscription.add(session, new_user.id, customer_id, subscription_id, "month",
                                     UserSubscriptionStatus.Paused)

            # Mock the Stripe API response
            event = {
                "type": "customer.subscription.resumed",
                "data": {
                    "object": {
                        "id": subscription_id,
                        "customer": customer_id,
                        "status": "active",
                    }
                }
            }
            stripe.Webhook.construct_event = MagicMock(return_value=event)

            # Simulate a request to the checkout session endpoint
            response = client.post('/api/v1/webhook/stripe-event', json=event, headers={
                "Stripe-Signature": "t=1234567890,v1=1234567890,v0=1234567890"
            })

            # Assert the response
            assert response.status_code == 200

        def test_customer_subscription_updated(self, client, new_user):
            customer_id = "cus_test_123"
            subscription_id = "sub_test_123"
            with get_session(write=True) as session:
                User.update(session, new_user.id, stripe_customer_id=customer_id)
                UserSubscription.add(session, new_user.id, customer_id, subscription_id, "month",
                                     UserSubscriptionStatus.Trialing)

            # Mock the Stripe API response
            event = {
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": subscription_id,
                        "customer": customer_id,
                        "status": "active",
                        "items": {
                            "data": [
                                {
                                    "plan": {
                                        "interval": "month",
                                    }
                                }
                            ]
                        }
                    }
                }
            }
            stripe.Webhook.construct_event = MagicMock(return_value=event)

            # Simulate a request to the checkout session endpoint
            response = client.post('/api/v1/webhook/stripe-event', json=event, headers={
                "Stripe-Signature": "t=1234567890,v1=1234567890,v0=1234567890"
            })

            # Assert the response
            assert response.status_code == 200

        def test_customer_subscription_deleted(self, client, new_user):
            customer_id = "cus_test_123"
            subscription_id = "sub_test_123"
            with get_session(write=True) as session:
                User.update(session, new_user.id, stripe_customer_id=customer_id)
                UserSubscription.add(session, new_user.id, customer_id, subscription_id, "month",
                                     UserSubscriptionStatus.Active)

            # Mock the Stripe API response
            event = {
                "type": "customer.subscription.deleted",
                "data": {
                    "object": {
                        "id": subscription_id,
                        "customer": customer_id,
                        "status": "canceled",
                    }
                }
            }
            stripe.Webhook.construct_event = MagicMock(return_value=event)

            # Simulate a request to the checkout session endpoint
            response = client.post('/api/v1/webhook/stripe-event', json=event, headers={
                "Stripe-Signature": "t=1234567890,v1=1234567890,v0=1234567890"
            })

            # Assert the response
            assert response.status_code == 200
