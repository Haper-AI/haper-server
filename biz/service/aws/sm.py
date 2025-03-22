import json

import boto3

from biz.utils.env import RuntimeEnv

_outlook_sub_private: str

_outlook_sub_public_b64: str


def load_secret():
    kms_client = boto3.client(
        "secretsmanager",
        region_name=RuntimeEnv.Instance().AWS_SM_REGION,
        aws_access_key_id=RuntimeEnv.Instance().AWS_ACCESS_KEY_ID,
        aws_secret_access_key=RuntimeEnv.Instance().AWS_SECRET_ACCESS_KEY,
    )
    secret_value_resp = kms_client.get_secret_value(
        SecretId=RuntimeEnv.Instance().AWS_SM_SECRET_NAME
    )
    secret_values = json.loads(secret_value_resp["SecretString"])
    global _outlook_sub_private
    _outlook_sub_private = secret_values[RuntimeEnv.Instance().AWS_SM_KEY_NAME_OUTLOOK_SUB_PRIVATE]

    global _outlook_sub_public_b64
    _outlook_sub_public_b64 = secret_values[RuntimeEnv.Instance().AWS_SM_KEY_NAME_OUTLOOK_SUB_PUBLIC]


def get_outlook_sub_private():
    return _outlook_sub_private


def get_outlook_sub_public_b64():
    return _outlook_sub_public_b64
