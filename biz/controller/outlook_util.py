import asyncio
from datetime import datetime, timezone, timedelta

import requests
from msgraph.generated.models.body_type import BodyType
from msgraph.generated.models.email_address import EmailAddress
from msgraph.generated.models.item_body import ItemBody
from msgraph.generated.models.message import Message
from msgraph.generated.models.recipient import Recipient
from msgraph.generated.models.subscription import Subscription
from msgraph.generated.users.item.messages.item.reply.reply_post_request_body import ReplyPostRequestBody

from biz.controller.mail_util_base import ExtractedMail, EmailBodyType
from biz.service.aws.sm import get_outlook_sub_public_b64
from biz.utils import extract_visible_text_from_email
from biz.utils.env import RuntimeEnv
from msgraph import GraphServiceClient
from azure.core.credentials import AccessToken


class OutlookInfo(ExtractedMail):
    def __init__(self):
        super().__init__()


def extract_outlook_info(email_info: Message, clean_html=True) -> OutlookInfo:
    extracted_outlook_info = OutlookInfo()
    extracted_outlook_info.message_id = email_info.id
    extracted_outlook_info.thread_id = email_info.conversation_id
    extracted_outlook_info.receive_at = email_info.received_date_time
    sender_info_dict = email_info.sender.email_address
    extracted_outlook_info.sender_name = sender_info_dict.name
    extracted_outlook_info.sender_email = sender_info_dict.address
    extracted_outlook_info.sender = "{} <{}>".format(extracted_outlook_info.sender_name,
                                                     extracted_outlook_info.sender_email)
    recipient_info_dict = email_info.to_recipients[0].email_address
    extracted_outlook_info.to = recipient_info_dict.address
    extracted_outlook_info.subject = email_info.subject
    body_info_dict = email_info.body

    # get body type and do cleaning if needed
    if body_info_dict.content_type == BodyType.Html:
        extracted_outlook_info.mime_type = EmailBodyType.Html
        if clean_html:
            extracted_outlook_info.cleaned_body = extract_visible_text_from_email(body_info_dict.content)
    elif body_info_dict.content_type == BodyType.Text:
        extracted_outlook_info.mime_type = EmailBodyType.Text

    extracted_outlook_info.body = body_info_dict.content
    if not extracted_outlook_info.cleaned_body: # assign cleaned body to body if not already set
        extracted_outlook_info.cleaned_body = extracted_outlook_info.body

    return extracted_outlook_info


_RefreshAccessTokenEndpoint = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'


class RawAccessTokenProvider:
    """
    A simple credential provider that returns a raw access token for use with Azure SDK clients.
    """

    def __init__(self, access_token: str, refresh_token: str, expires_at: int) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at

    def get_token(self, *scopes, **kwargs) -> AccessToken:
        if int(datetime.now().timestamp()) > self.expires_at:
            refresh_response = requests.post(_RefreshAccessTokenEndpoint, data={
                'client_id': RuntimeEnv.Instance().MICROSOFT_CLIENT_ID,
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token,
                'client_secret': RuntimeEnv.Instance().MICROSOFT_CLIENT_SECRET,
            })
            resp_json = refresh_response.json()
            if "access_token" in resp_json:
                self.access_token = resp_json["access_token"]
            if "expires_in" in resp_json:
                self.expires_at = int(datetime.now().timestamp()) + resp_json["expires_in"]
            if "refresh_token" in resp_json:
                self.refresh_token = resp_json["refresh_token"]
        return AccessToken(self.access_token, self.expires_at)


class OutlookAPIClient:
    def __init__(self, access_token: str, refresh_token: str, expires_at: int):
        self.credential = RawAccessTokenProvider(access_token, refresh_token, expires_at)
        self.client = GraphServiceClient(self.credential)

    @property
    def access_token(self) -> str:
        return self.credential.access_token

    @property
    def refresh_token(self) -> str:
        return self.credential.refresh_token

    @property
    def expires_at(self) -> int:
        return self.credential.expires_at

    def watch_outlook(self):
        # see more from: https://learn.microsoft.com/en-us/graph/api/subscription-post-subscriptions?view=graph-rest-1.0&tabs=python#tabpanel_1_python
        watch_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10070)
        request_body = Subscription(
            change_type="created",
            notification_url=RuntimeEnv.Instance().OUTLOOK_SYNC_WEBHOOK_URL,
            # for Outlook mail resource: see more from: https://learn.microsoft.com/en-us/graph/api/resources/change-notifications-api-overview?view=graph-rest-1.0
            resource="me/mailFolders('Inbox')/messages?$select=toRecipients",
            # for expiration, see more from: https://learn.microsoft.com/en-us/graph/api/resources/subscription?view=graph-rest-1.0#subscription-lifetime
            expiration_date_time=watch_expires_at,
            latest_supported_tls_version="v1_2",
            include_resource_data=True,
            encryption_certificate_id=RuntimeEnv.Instance().MICROSOFT_CERTIFICATE_KEY_ID,
            encryption_certificate=get_outlook_sub_public_b64(),
        )
        subscribe = asyncio.run(self.client.subscriptions.post(request_body))
        subscription_id = subscribe.id
        return subscription_id, int(watch_expires_at.timestamp())

    def refresh_watch_outlook(self, subscription_id: str):
        watch_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10070)  # 10 minutes less than 1 week
        request_body = Subscription(
            expiration_date_time=watch_expires_at,
        )
        asyncio.run(self.client.subscriptions.by_subscription_id(subscription_id).patch(request_body))
        return int(watch_expires_at.timestamp())

    def stop_watch_outlook(self, subscription_id: str):
        asyncio.run(self.client.subscriptions.by_subscription_id(subscription_id).delete())

    def get_email(self, message_id: str):
        return asyncio.run(self.client.me.messages.by_message_id(message_id).get())

    def read_email(self, message_id: str):
        req_body = Message(
            is_read=True,
        )
        asyncio.run(self.client.me.messages.by_message_id(message_id).patch(req_body))

    def trash_email(self, message_id: str):
        asyncio.run(self.client.me.messages.by_message_id(message_id).delete())

    def reply_email_text(self, message_id: str, recipient_name: str, recipient_address: str, text_payload: str):
        req_body = ReplyPostRequestBody(
            message=Message(
                to_recipients=[
                    Recipient(
                        email_address=EmailAddress(
                            name=recipient_name,
                            address=recipient_address,
                        )
                    )
                ],
                body=ItemBody(
                    content_type=BodyType.Text,
                    content=text_payload,
                )
            )
        )
        asyncio.run(self.client.me.messages.by_message_id(message_id).reply.post(req_body))
