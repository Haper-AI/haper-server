import base64
import json
import random
from datetime import datetime, timezone, timedelta
from email.utils import formatdate
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from msgraph.generated.models.body_type import BodyType
from msgraph.generated.models.email_address import EmailAddress
from msgraph.generated.models.item_body import ItemBody
from msgraph.generated.models.message import Message
from msgraph.generated.models.recipient import Recipient
from sqlalchemy.orm import make_transient

from app.consumer_main import handle_report_update
from biz.controller.gmail_util import GmailAPIClient
from biz.controller.outlook_util import OutlookAPIClient
from biz.controller.report_update import example_summary
from biz.dal.email import Email
from biz.dal.report import Report, MessageCategory, MessageAction
from biz.dal.user import User, Account, AccountProvider
from haper_script.schema_gen.python import report_update_message as rum_model
from biz.service.db import get_session
from haper_script.schema_gen.python import report as report_model
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
    mock_chat_model.invoke.side_effect = invoke_return

    with patch('biz.controller.report_update.init_chat_model', return_value=mock_chat_model) as mock_init_chat_model:
        yield mock_init_chat_model


@pytest.fixture
def patch_langchain_embedding_model():
    mock_embedding_model = MagicMock()
    mock_embedding_model.embed_query.side_effect = [embeddings] * 3

    with patch('biz.controller.report_update.init_embeddings',
               return_value=mock_embedding_model) as mock_init_embedding_model:
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
    with patch.object(GmailAPIClient, "client", create=True, new_callable=PropertyMock) as p1:
        with patch.object(GmailAPIClient, "credential", create=True, new_callable=PropertyMock) as p2:
            p1.return_value = mock_gmail_client
            p2.return_value = mock_credential
            yield p1, p2


@pytest.mark.usefixtures("patch_langchain_chat_model")
@pytest.mark.usefixtures("patch_langchain_embedding_model")
@pytest.mark.usefixtures("patch_gmail_get_message")
def test_handle_report_update_gmail_message():
    email = generate_random_gmail(10)
    report_obj = report_model.Report(
        messages_in_queue={
            "gmail": 3
        },
        summary=[],
        content=report_model.ReportContent(
            content_sources=[],
            gmail=None,
            outlook=None,
        )
    )
    with get_session(write=True) as session:
        user = User.add(session, generate_random_string(5), email)
        account = Account.add(
            session, user.id, AccountProvider.Google, generate_random_string(16),
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
                receive_at=datetime.now(timezone.utc),
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
                receive_at=datetime.now(timezone.utc),
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
        user_id=str(user.id),
        report_id=str(report.id),
        messages=rum_model.Messages(
            gmail=rum_model.Gmail(
                account_id=account.id,
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
            ),
            outlook=None
        ),
    )

    handle_report_update(report_update_message)


@pytest.fixture
def patch_outlook_get_message():
    mock_outlook_client = MagicMock()

    async def email_data_1():
        msg = Message()
        msg.id = "outlook_email_id_1"
        msg.conversation_id = "outlook_conversation_id_1"
        msg.received_date_time = datetime.now()
        msg.sender = Recipient()
        msg.sender.email_address = EmailAddress()
        msg.sender.email_address.name = "some sender 1"
        msg.sender.email_address.address = "somesender.1@outlook.com"
        msg.to_recipients = [Recipient()]
        msg.to_recipients[0].email_address = EmailAddress()
        msg.to_recipients[0].email_address.name = "some recipient 1"
        msg.to_recipients[0].email_address.address = "somereceiver.1@outlook.com"
        msg.subject = "some subject 1"
        msg.body = ItemBody()
        msg.body.content_type = BodyType.Text
        msg.body.content = "some content 1"

        return msg

    async def email_data_2():
        msg = Message()
        msg.id = "outlook_email_id_2"
        msg.conversation_id = "outlook_conversation_id_2"
        msg.received_date_time = datetime.now()
        msg.sender = Recipient()
        msg.sender.email_address = EmailAddress()
        msg.sender.email_address.name = "some sender 2"
        msg.sender.email_address.address = "somesender.2@outlook.com"
        msg.to_recipients = [Recipient()]
        msg.to_recipients[0].email_address = EmailAddress()
        msg.to_recipients[0].email_address.name = "some recipient 2"
        msg.to_recipients[0].email_address.address = "somereceiver.2@outlook.com"
        msg.subject = "some subject 2"
        msg.body = ItemBody()
        msg.body.content_type = BodyType.Html
        msg.body.content = """
                    <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
                    <html xmlns="http://www.w3.org/1999/xhtml"
                    xmlns:v="urn:schemas-microsoft-com:vml"
                    xmlns:o="urn:schemas-microsoft-com:office:office">
                    <head>
                    </head>
                    <body>
                    </body>
                    </html>
                    """

        return msg

    async def email_data_3():
        msg = Message()
        msg.id = "outlook_email_id_3"
        msg.conversation_id = "outlook_conversation_id_3"
        msg.received_date_time = datetime.now()
        msg.sender = Recipient()
        msg.sender.email_address = EmailAddress()
        msg.sender.email_address.name = "some sender 3"
        msg.sender.email_address.address = "somesender.3@outlook.com"
        msg.to_recipients = [Recipient()]
        msg.to_recipients[0].email_address = EmailAddress()
        msg.to_recipients[0].email_address.name = "some recipient 3"
        msg.to_recipients[0].email_address.address = "somereceiver.3@outlook.com"
        msg.subject = "some subject 3"
        msg.body = ItemBody()
        msg.body.content_type = BodyType.Text
        msg.body.content = "some content 3"

        return msg

    mock_outlook_client.me.messages.by_message_id.return_value.get.side_effect = [
        email_data_1(),
        email_data_2(),
        email_data_3(),
    ]

    mock_credential = MagicMock()
    mock_credential.access_token = generate_random_string(10)
    mock_credential.refresh_token = generate_random_string(10)
    mock_credential.expires_at = int((datetime.now() + timedelta(hours=2)).timestamp())
    with patch.object(OutlookAPIClient, "client", create=True, new_callable=PropertyMock) as p1:
        with patch.object(OutlookAPIClient, "credential", create=True, new_callable=PropertyMock) as p2:
            p1.return_value = mock_outlook_client
            p2.return_value = mock_credential
            yield p1, p2


@pytest.mark.usefixtures("patch_langchain_chat_model")
@pytest.mark.usefixtures("patch_langchain_embedding_model")
@pytest.mark.usefixtures("patch_outlook_get_message")
def test_handle_report_update_outlook_message():
    email = generate_random_gmail(10)
    report_obj = report_model.Report(
        messages_in_queue={
            "outlook": 3
        },
        summary=[],
        content=report_model.ReportContent(
            content_sources=[],
            gmail=None,
            outlook=None
        )
    )
    with get_session(write=True) as session:
        user = User.add(session, generate_random_string(5), email)
        account = Account.add(
            session, user.id, AccountProvider.Microsoft, generate_random_string(16),
            "access_token", "refresh_token",
            expires_at=int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            email=email
        )
        report = Report.add(session, user.id, report_obj.to_dict())
        emails = [
            Email(
                user_id=user.id,
                source="outlook",
                message_id="message-id-1",
                thread_id="message-id-1",
                sender="someone <someone@gmail.com>",
                receiver=email,
                subject="some subject",
                receive_at=datetime.now(timezone.utc),
                tags=["tag1", "tag2"],
                summary="some summary",
                summary_embedding=embeddings,
                llm_category=MessageCategory.Essential,
                llm_action=MessageAction.Read
            ),
            Email(
                user_id=user.id,
                source="outlook",
                message_id="message-id-2",
                thread_id="message-id-2",
                sender="someone <someone@gmail.com>",
                receiver=email,
                subject="some subject",
                receive_at=datetime.now(timezone.utc),
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
        user_id=str(user.id),
        report_id=str(report.id),
        messages=rum_model.Messages(
            gmail=None,
            outlook=rum_model.Outlook(
                account_id=account.id,
                new_messages=["outlook_email_id_1", "outlook_email_id_2", "outlook_email_id_3"],
            )
        ),
    )

    handle_report_update(report_update_message)
