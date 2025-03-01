import base64
import json
import uuid
from datetime import timedelta, datetime

from .conftest import *
from tests import generate_random_string, generate_random_gmail
from unittest.mock import patch, MagicMock


class TestGmailSyncWebhook:
    @patch('biz.controller.message_sync.build_gmail_client')
    @patch('biz.dal.user.Account.get_by_gmail', return_value=MagicMock())
    def test_success(self, mock_account_get_by_gmail, mock_build_gmail_client, client):
        # configure account table
        mock_account = MagicMock()
        mock_account.id = uuid.uuid4()
        mock_account.access_token = generate_random_string(10)
        mock_account.refresh_token = generate_random_string(10)
        mock_account.expires_at = (datetime.now() + timedelta(hours=1)).timestamp()
        mock_account.user_id = generate_random_string(10)
        mock_account.provider = 'gmail'
        mock_account.provider_account_id = generate_random_string(10)
        mock_account_get_by_gmail.return_value = mock_account


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
