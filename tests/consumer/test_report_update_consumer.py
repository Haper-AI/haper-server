import base64
import json
import random
from datetime import datetime, timezone, timedelta
from email.utils import formatdate
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import make_transient

from app.report_update_consumer import handle_message
from biz.controller.report_update import example_summary
from biz.dal.email import Email
from biz.dal.report import Report, MessageCategory, MessageAction
from biz.dal.user import User, Account
from biz.model.report import report_update_message as rum_model
from biz.service.db import get_session
from biz.model.report import report as report_model
from tests import generate_random_gmail, generate_random_string

class ObjectWithContent:
    def __init__(self, content):
        self.content = content

embeddings = [random.uniform(-1, 1) for _ in range(768)]

@pytest.fixture
def patch_langchain_chat_model():
    mock_chat_model = MagicMock()

    invoke_return = [
        ObjectWithContent(json.dumps({
            "summary": "some summary 1",
            "tags": ["tag1", "tag2"],
        })),
        ObjectWithContent(json.dumps({
            "category": MessageCategory.Essential,
            "action": MessageAction.Read,
        })),
        ObjectWithContent(json.dumps({
            "summary": "some summary 2",
            "tags": ["tag3", "tag4"],
        })),
        ObjectWithContent(json.dumps({
            "category": MessageCategory.NonEssential,
            "action": MessageAction.Reply,
        })),
        ObjectWithContent(json.dumps({
            "summary": "some summary 3",
            "tags": ["tag4", "tag5"],
        })),
        ObjectWithContent(json.dumps({
            "category": MessageCategory.NonEssential,
            "action": MessageAction.Reply,
        })),
        ObjectWithContent(example_summary)
    ]
    mock_chat_model.invoke.side_effect=invoke_return

    with patch('biz.controller.report_update.init_chat_model', return_value=mock_chat_model) as mock_init_chat_model:
        yield mock_init_chat_model


@pytest.fixture
def patch_langchain_embedding_model():
    mock_embedding_model = MagicMock()
    mock_embedding_model.invoke.side_effect = [embeddings] * 3

    with patch('biz.controller.report_update.init_embeddings', return_value=mock_embedding_model) as mock_init_embedding_model:
        yield mock_init_embedding_model


@pytest.fixture
def patch_gmail_get_message():
    mock_gmail_client = MagicMock()
    mock_gmail_client.users().messages().get.return_value.execute = MagicMock(side_effect=[
        # email data 1
        {
            "snippet": "some snippet 1",
            "labelIds": [
                "CATEGORY_PROMOTIONS",
                "IMPORTANT",
            ],
            "payload": {
                "headers": [
                    {
                        "name": "Date",
                        "value": formatdate(timeval=datetime.now().timestamp(), localtime=True, usegmt=False),
                    },
                    {
                        "name": "Subject",
                        "value": "some subject 1",
                    },
                    {
                        "name": "From",
                        "value": "some one 1 <someone.1@gmail.com>",
                    },
                    {
                        "name": "To",
                        "value": "receiver@gmail.com"
                    }
                ],
                "mimeType": "text/plain",
                "body": {
                    "size": 20,
                    "data": base64.urlsafe_b64encode("Some email body data".encode("utf-8")).decode("utf-8")
                }
            }
        },
        # email data 2
        {
            "snippet": "some snippet 2",
            "labelIds": [
                "INBOX",
                "IMPORTANT",
            ],
            "payload": {
                "headers": [
                    {
                        "name": "Date",
                        "value": formatdate(timeval=datetime.now().timestamp(), localtime=True, usegmt=False)
                    },
                    {
                        "name": "Subject",
                        "value": "some subject 2",
                    },
                    {
                        "name": "From",
                        "value": "some one 2 <someone.2@gmail.com>",
                    },
                    {
                        "name": "To",
                        "value": "receiver@gmail.com"
                    }
                ],
                "mimeType": "text/html",
                "body": {
                    "size": 20,
                    "data": base64.urlsafe_b64encode("""
                    <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
                    <html xmlns="http://www.w3.org/1999/xhtml"
                    xmlns:v="urn:schemas-microsoft-com:vml"
                    xmlns:o="urn:schemas-microsoft-com:office:office">
                    <head>
                    </head>
                    <body>
                    </body>
                    </html>
                    """.encode("utf-8")).decode("utf-8")
                }
            }
        },
        # email data 3
        {
            "snippet": "some snippet 2",
            "labelIds": [
                "INBOX",
                "IMPORTANT",
            ],
            "payload": {
                "headers": [
                    {
                        "name": "Date",
                        "value": formatdate(timeval=datetime.now().timestamp(), localtime=True, usegmt=False)
                    },
                    {
                        "name": "Subject",
                        "value": "some subject 2",
                    },
                    {
                        "name": "From",
                        "value": "some one 2 <someone.2@gmail.com>",
                    },
                    {
                        "name": "To",
                        "value": "receiver@gmail.com"
                    }
                ],
                "mimeType": "multipart/alternative",
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {
                            "size": 20,
                            "data": base64.urlsafe_b64encode("Some email body data".encode("utf-8")).decode("utf-8")
                        }
                    },
                    {
                        "mimeType": "text/html",
                        "body": {
                            "size": 20,
                            "data": base64.urlsafe_b64encode("""
                        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
                        <html xmlns="http://www.w3.org/1999/xhtml"
                        xmlns:v="urn:schemas-microsoft-com:vml"
                        xmlns:o="urn:schemas-microsoft-com:office:office">
                        <head>
                        </head>
                        <body>
                        </body>
                        </html>
                        """.encode("utf-8")).decode("utf-8")
                        }
                    }
                ]
            }
        },
    ])

    mock_credential = MagicMock()
    mock_credential.token = generate_random_string(10)
    mock_credential.expiry = datetime.now() + timedelta(hours=2)
    with patch('app.report_update_consumer.build_gmail_client',
               return_value=(mock_gmail_client, mock_credential)) as mock_build_gmail_account:
        yield mock_build_gmail_account


@pytest.mark.usefixtures("patch_langchain_chat_model")
@pytest.mark.usefixtures("patch_langchain_embedding_model")
@pytest.mark.usefixtures("patch_gmail_get_message")
def test_handle_report_update_message():
    email = generate_random_gmail(10)
    report_obj = report_model.Report(
        messages_in_queue={
            "gmail": 3
        },
        summary=[],
        content=report_model.ReportContent(
            content_sources=[],
            gmail=None
        )
    )
    with get_session(write=True) as session:
        user = User.add(session, generate_random_string(5), email)
        account = Account.add(session, user.id, "google", generate_random_string(16),
                              "access_token", "refresh_token",
                              expires_at=int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
                              email=email
                              )
        report = Report.add(session, user.id, report_obj.to_dict())
        emails = [
            Email(
                user_id=user.id,
                source="gmail",
                message_id="message-id-1",
                thread_id="message-id-1",
                sender="someone <someone@gmail.com>",
                receiver=email,
                subject="some subject",
                received_at=datetime.now(timezone.utc),
                tags=["tag1", "tag2"],
                summary="some summary",
                summary_embedding=embeddings,
                llm_category=MessageCategory.Essential,
                llm_action=MessageAction.Read
            ),
            Email(
                user_id=user.id,
                source="gmail",
                message_id="message-id-2",
                thread_id="message-id-2",
                sender="someone <someone@gmail.com>",
                receiver=email,
                subject="some subject",
                received_at=datetime.now(timezone.utc),
                tags=["tag3", "tag4"],
                summary="some summary",
                summary_embedding=embeddings,
                llm_category=MessageCategory.Essential,
                llm_action=MessageAction.Read
            )
        ]
        session.add_all(emails)
        make_transient(user), make_transient(account), make_transient(report)

    report_update_message = rum_model.ReportUpdateMessage(
        user_info=rum_model.UserInfo(user_id=str(user.id)),
        report_info=rum_model.ReportInfo(report_id=str(report.id)),
        messages=rum_model.Messages(
            gmail=rum_model.Gmail(
                account_info=rum_model.AccountInfo(
                    account_id=account.id
                ),
                new_messages=[
                    rum_model.GmailNewMessage(
                        message_id="1",
                        thread_id="1",
                    ),
                    rum_model.GmailNewMessage(
                        message_id="2",
                        thread_id="2",
                    ),
                    rum_model.GmailNewMessage(
                        message_id="3",
                        thread_id="3",
                    )
                ],
            )
        ),
    )

    handle_message(report_update_message)
