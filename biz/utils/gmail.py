from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from .env import RuntimeEnv

def build_gmail_client(access_token, refresh_token, expiry):
    credential = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        expiry=expiry,
        token_uri="https://accounts.google.com/o/oauth2/token",
        client_id=RuntimeEnv.Instance().GOOGLE_CLIENT_ID,
        client_secret=RuntimeEnv.Instance().GOOGLE_CLIENT_SECRET
    )
    return build('gmail', 'v1', credentials=credential), credential