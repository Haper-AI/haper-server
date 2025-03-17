import json
import uuid

import boto3
from botocore.client import BaseClient

from biz.model.report import sqs_message as sqs_message_model
from biz.model.report.report_batch_action_message import ReportBatchActionMessage
from biz.model.report.report_update_message import ReportUpdateMessage
from biz.model.report.sqs_message import ActionType
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


def send_report_update_message(message: ReportUpdateMessage, report_id: str):
    sqs_message_obj = sqs_message_model.SqsMessage(
        action_type=ActionType.REPORT_UPDATE,
        report_update_message=message,
        report_batch_action_message=None
    )
    _sqs_client.send_message(
        QueueUrl=RuntimeEnv.Instance().SQS_REPORT_UPDATE_QUEUE_URL,
        MessageBody=json.dumps(sqs_message_obj.to_dict()),
        # MessageGroupId and message MessageDeduplicationId will make sure message that will update the same report
        # will be sent to the same consumer so that it can avoid concurrency issue for report updating.
        # But this will also require the sqs queue be a FIFO queue
        MessageGroupId=report_id,
        # As we use ContentBasedDeduplication for sqs queue, we can skip creating our own
        # MessageDeduplicationId=str(uuid.uuid4()) if report_id else None,
    )

def send_report_batch_action_message(message: ReportBatchActionMessage, report_id: str):
    sqs_message_obj = sqs_message_model.SqsMessage(
        action_type=ActionType.REPORT_BATCH_ACTION,
        report_update_message=None,
        report_batch_action_message=message
    )

    _sqs_client.send_message(
        QueueUrl=RuntimeEnv.Instance().SQS_REPORT_UPDATE_QUEUE_URL,
        MessageBody=json.dumps(sqs_message_obj.to_dict()),
        MessageGroupId=report_id,
    )
