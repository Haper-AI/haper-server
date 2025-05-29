import json
import time
from typing import Optional, List

from flask import Blueprint, request, Response
from pydantic import BaseModel, PositiveInt

from biz.controller import report as report_ctrl
from biz.dal.report_batch_action import BatchActionRunStatus
from biz.handler.middleware import catch_error, user_auth
from biz.model import ReportFieldName
from biz.service.rate_limiter import user_limiter
from biz.utils.logger import logger
from biz.utils.response import HTTPResponse

report_routes = Blueprint("report_api", __name__, url_prefix="/report")


def report_to_resp_dict(report):
    return {
        "id": str(report.id),
        "content": report.content,
        "status": report.status,
        "created_at": report.created_at,
        "finalized_at": report.finalized_at,
        "last_access_at": report.last_access_at,
    }


@report_routes.route("/newest")
@catch_error
@user_auth()
def get_newest_appending_report():
    resp = HTTPResponse(request.method, request.path)
    report = report_ctrl.get_newest_report(request.ctx.user_id)
    if report:
        resp.set_data({
            "report": report_to_resp_dict(report),
        })
    else:
        resp.set_data({
            "report": None
        })
    return resp.return_with_log()


@report_routes.route("/generate", methods=["POST"])
@catch_error
@user_auth()
@user_limiter.limit("10 per day")
def generate_report():
    resp = HTTPResponse(request.method, request.path)
    latest_report, _ = report_ctrl.generate_report(request.ctx.user_id)
    resp.set_data({
        "report": report_to_resp_dict(latest_report),
    })
    return resp.return_with_log()


class ListReportHistoryReq(BaseModel):
    page: Optional[PositiveInt] = 1
    page_size: Optional[PositiveInt] = 10


@report_routes.route("/history", methods=["GET"])
@catch_error
@user_auth()
def list_reports_history():
    resp = HTTPResponse(request.method, request.path)
    req = ListReportHistoryReq(**request.args.to_dict())
    reports, count = report_ctrl.list_history_reports(request.ctx.user_id, req.page, req.page_size)
    resp.set_data({
        "reports": [report_to_resp_dict(r) for r in reports],
        "total_page": count // req.page_size,
    })
    return resp.return_with_log()


@report_routes.route("/<uuid:report_id>", methods=["GET"])
@catch_error
@user_auth()
def get_report_by_id(report_id: str):
    resp = HTTPResponse(request.method, request.path)
    report = report_ctrl.get_report_by_id(request.ctx.user_id, report_id, for_access=True)
    resp.set_data({
        "report": report_to_resp_dict(report),
    })
    return resp.return_with_log()


def poll_message_processing_status(pre_status: dict, report_id: str):
    yield json.dumps(pre_status)
    has_message_in_queue = False
    for k, v in pre_status.items():
        if v > 0:
            has_message_in_queue = True
            break
    try:
        while has_message_in_queue:
            time.sleep(1)
            new_status = report_ctrl.poll_report_messages_in_queue_status(report_id)
            has_update = False
            has_message_in_queue = False
            for k, v in new_status.items():
                if pre_status[k] != v:
                    has_update = True
                if v > 0:
                    has_message_in_queue = True

            if has_update:
                yield json.dumps(new_status)
                pre_status = new_status
    except GeneratorExit:
        logger.info("Client disconnected")


@report_routes.route("/<uuid:report_id>/message-processing-status", methods=["POST"])
# as DigitalOcean App Platform will buffer all response and then return all data when method is GET for event-stream
# we use post temporally to solve this problem right now
@catch_error
@user_auth()
def message_processing_status(report_id: str):
    report = report_ctrl.get_report_by_id(request.ctx.user_id, report_id)

    return Response(poll_message_processing_status(report.content.get(ReportFieldName.MessagesInQueue, {}), report_id),
                    content_type="text/event-stream")


@report_routes.route("/<uuid:report_id>", methods=["DELETE"])
@catch_error
@user_auth()
def delete_report_by_id(report_id: str):
    resp = HTTPResponse(request.method, request.path)
    report_ctrl.delete_report_by_id(request.ctx.user_id, report_id)
    return resp.return_with_log()


@report_routes.route("/<uuid:report_id>", methods=["PUT"])
@catch_error
@user_auth()
@user_limiter.limit("4 per 1 second")
def update_report_info(report_id: str):
    resp = HTTPResponse(request.method, request.path)
    req = report_ctrl.ReportUpdateInfo(**request.get_json())
    report_ctrl.update_report_info(request.ctx.user_id, report_id, req)
    return resp.return_with_log()


@report_routes.route("/<uuid:report_id>/batch-action", methods=["POST"])
@catch_error
@user_auth(check_subscription=False)
def report_batch_action(report_id: str):
    resp = HTTPResponse(request.method, request.path)
    run_id = report_ctrl.apply_report_actions(request.ctx.user_id, report_id)
    resp.set_data({
        "run_id": str(run_id),
    })
    return resp.return_with_log()


class BatchActionStatusInfos:
    def __init__(self, total: int, succeed: int, failed: int, logs: List[dict], status: BatchActionRunStatus):
        self.total = total
        self.succeed = succeed
        self.failed = failed
        self.logs = logs
        self.status = status

    def to_dict(self):
        return {
            "total": self.total,
            "succeed": self.succeed,
            "failed": self.failed,
            "status": self.status,
            # "logs": self.logs,
        }


def poll_batch_action_run_status(run_id: str, last_info: BatchActionStatusInfos):
    yield json.dumps(last_info.to_dict())
    if last_info.status != BatchActionRunStatus.Done:
        try:
            while True:
                time.sleep(1)
                run_status = report_ctrl.poll_last_batch_action(run_id)
                if run_status.logs is None:
                    run_status.logs = []
                has_updates = False
                if run_status.succeed_actions != last_info.succeed:
                    has_updates = True
                    last_info.succeed = run_status.succeed_actions
                if run_status.failed_actions != last_info.failed:
                    has_updates = True
                    last_info.failed = run_status.failed_actions
                if len(run_status.logs) != len(last_info.logs):
                    has_updates = True
                    last_info.logs = run_status.logs
                if run_status.status != last_info.status:
                    last_info.status = run_status.status

                if has_updates:
                    yield json.dumps(last_info.to_dict())

                if run_status.status == BatchActionRunStatus.Done:
                    logger.info("Poll batch action run status is done")
                    break
        except GeneratorExit:
            logger.info("Client disconnected")


@report_routes.route("/<uuid:report_id>/batch-action-status", methods=["POST"])
# as DigitalOcean App Platform will buffer all response and then return all data when method is GET for event-stream
# we use post temporally to solve this problem right now
@catch_error
@user_auth()
def report_batch_action_status(report_id: str):
    batch_run = report_ctrl.get_latest_batch_action(request.ctx.user_id, report_id)
    if batch_run is None:
        resp = HTTPResponse(request.method, request.path)
        return resp.return_with_log()

    return Response(poll_batch_action_run_status(str(batch_run.id), BatchActionStatusInfos(
        total=batch_run.total_actions,
        succeed=batch_run.succeed_actions,
        failed=batch_run.failed_actions,
        logs=batch_run.logs if batch_run.logs else [],
        status=batch_run.status,
    )), content_type="text/event-stream")


class GenerateMessageReplyReq(BaseModel):
    source: str
    account_id: str
    id: int


@report_routes.route("/<uuid:report_id>/generate-reply", methods=["POST"])
@catch_error
@user_auth(check_subscription=False)
@user_limiter.limit("1 per 3 second;100 per day")
def generate_message_reply(report_id: str):
    req = GenerateMessageReplyReq(**request.get_json())
    streaming_reply_gen = report_ctrl.generate_message_reply(
        request.ctx.user_id,
        report_id,
        req.source,
        req.account_id,
        req.id,
    )
    return Response(streaming_reply_gen(), content_type="text/event-stream")


class GetMessageContentReq(BaseModel):
    source: str
    account_id: str
    id: int


@report_routes.route("/<uuid:report_id>/message-content")
@catch_error
@user_auth()
@user_limiter.limit("2 per 1 second")
def get_message_content(report_id: str):
    resp = HTTPResponse(request.method, request.path)
    req = GetMessageContentReq(**request.args.to_dict())
    _, extracted_email = report_ctrl.get_message_content(
        request.ctx.user_id,
        report_id,
        req.source,
        req.account_id,
        req.id,
    )
    resp.set_data({
        "message_content": {
            "subject": extracted_email.subject,
            "from": extracted_email.sender,
            "to": extracted_email.to,
            "mime_type": extracted_email.mime_type,
            "body": extracted_email.body,
        }
    })
    return resp.return_with_log()

__all__ = ['report_routes']
