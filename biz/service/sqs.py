import uuid

import boto3
from botocore.client import BaseClient

from biz.utils.env import RuntimeEnv

_sqs_client: BaseClient


def init_sqs():
    global _sqs_client
    _sqs_client = boto3.client(
        'sqs',
        region_name=RuntimeEnv.Instance().SQS_REGION,
        endpoint_url=RuntimeEnv.Instance().SQS_ENDPOINT,
        aws_access_key_id=RuntimeEnv.Instance().AWS_ACCESS_KEY_ID,
        aws_secret_access_key=RuntimeEnv.Instance().AWS_ACCESS_KEY_ID,
    )


def get_sqs_client():
    return _sqs_client


def send_report_update_message(message: str, report_id: str):
    _sqs_client.send_message(
        QueueUrl=RuntimeEnv.Instance().SQS_REPORT_UPDATE_QUEUE_URL,
        MessageBody=message,
        # MessageGroupId and message MessageDeduplicationId will make sure message that will update the same report
        # will be sent to the same consumer so that it can avoid concurrency issue for report updating.
        # But this will also require the sqs queue be a FIFO queue
        MessageGroupId=report_id,
        # As we use ContentBasedDeduplication for sqs queue, we can skip creating our own
        # MessageDeduplicationId=str(uuid.uuid4()) if report_id else None,
    )
