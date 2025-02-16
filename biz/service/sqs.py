import boto3
from biz.utils.env import RuntimeEnv

sqs_client = boto3.client(
    'sqs',
    region_name=RuntimeEnv.Instance().SQS_REGION,
    endpoint_url=RuntimeEnv.Instance().SQS_ENDPOINT,
    aws_access_key_id=RuntimeEnv.Instance().AWS_ACCESS_KEY_ID,
    aws_secret_access_key=RuntimeEnv.Instance().AWS_ACCESS_KEY_ID,
)


def send_report_update_message(message: str):
    sqs_client.send_message(
        QueueUrl=RuntimeEnv.Instance().SQS_REPORT_UPDATE_QUEUE_URL,
        MessageBody=message,
    )
