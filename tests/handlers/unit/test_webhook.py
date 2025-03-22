import base64
import json
from datetime import timedelta, datetime

from biz.dal.report import Report
from biz.service.db import get_session
from tests import generate_random_string, generate_random_gmail
from unittest.mock import patch, MagicMock


class TestGmailSyncWebhook:
    @patch('biz.controller.message_sync.build_gmail_client')
    def test_success(self, mock_build_gmail_client, client, new_user_account):
        user, account = new_user_account
        with get_session(write=True) as session:
            Report.add(session, user.id , {})

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
