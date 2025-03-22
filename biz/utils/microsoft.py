from datetime import datetime

import requests
from msgraph import GraphServiceClient

from azure.core.credentials import AccessToken

from biz.utils.env import RuntimeEnv

_RefreshAccessTokenEndpoint = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'


class RawAccessTokenProvider:
    """
    A simple credential provider that returns a raw access token for use with Azure SDK clients.
    """

    def __init__(self, access_token: str, refresh_token: str, expiry: int) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expiry = expiry

    def get_token(self, *scopes, **kwargs) -> AccessToken:
        if int(datetime.now().timestamp()) > self.expiry:
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
                self.expiry = int(datetime.now().timestamp()) + resp_json["expires_in"]
            if "refresh_token" in resp_json:
                self.refresh_token = resp_json["refresh_token"]
        return AccessToken(self.access_token, self.expiry)


def build_microsoft_graph_client(access_token: str, refresh_token, expiry: int) -> [GraphServiceClient, AccessToken]:
    credential = RawAccessTokenProvider(access_token, refresh_token, expiry)
    return GraphServiceClient(credential), credential
