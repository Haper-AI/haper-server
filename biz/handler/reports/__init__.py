import json
import time
from typing import Optional, List

from flask import Blueprint, request, Response
from pydantic import BaseModel, PositiveInt

from biz.controller import report as report_ctrl
from biz.dal.report_batch_action import BatchActionRunStatus
from biz.handler.middleware import catch_error, jwt_auth
from biz.utils.logger import logger
from biz.utils.response import HTTPResponse

report_routes = Blueprint("report_api", __name__, url_prefix="/report")


# ---------------------- API routes ----------------------
@report_routes.route("/newest", methods=["GET"])
@catch_error
@jwt_auth
def get_newest_appending_report():
    resp = HTTPResponse(request.method, request.path)
    report = report_ctrl.get_newest_report(request.ctx.user_id)
    if report:
        resp.set_data({
            "report": {
                "id": str(report.id),
                "content": report.content,
                "status": report.status,
                "created_at": report.created_at,
            },
        })
    else:
        resp.set_data({
            "report": None
        })
    return resp.return_with_log()


@report_routes.route("/generate", methods=["POST"])
@catch_error
@jwt_auth
def generate_report():
    resp = HTTPResponse(request.method, request.path)
    latest_report, _ = report_ctrl.generate_report(request.ctx.user_id)
    resp.set_data({
        "report": {
            "id": str(latest_report.id),
            "content": latest_report.content,
            "created_at": latest_report.created_at,
            "finalized_at": latest_report.finalized_at,
        },
    })
    return resp.return_with_log()


class ListReportHistoryReq(BaseModel):
    page: Optional[PositiveInt] = 1
    page_size: Optional[PositiveInt] = 10


@report_routes.route("/history", methods=["GET"])
@catch_error
@jwt_auth
def list_reports_history():
    resp = HTTPResponse(request.method, request.path)
    req = ListReportHistoryReq(**request.args.to_dict())
    reports, count = report_ctrl.list_history_reports(request.ctx.user_id, req.page, req.page_size)
    resp.set_data({
        "reports": [{
            "id": str(r.id),
            "content": r.content,
            "created_at": r.created_at,
            "finalized_at": r.finalized_at,
        } for r in reports],
        "total_page": count // req.page_size,
    })
    return resp.return_with_log()


@report_routes.route("/<uuid:report_id>", methods=["GET"])
@catch_error
@jwt_auth
def get_report_by_id(report_id: str):
    resp = HTTPResponse(request.method, request.path)
    report = report_ctrl.get_report_by_id(request.ctx.user_id, report_id)
    resp.set_data({
        "report": {
            "id": str(report.id),
            "content": report.content,
            "status": report.status,
            "created_at": report.created_at,
            "finalized_at": report.finalized_at,
        },
    })
    return resp.return_with_log()


@report_routes.route("/<uuid:report_id>", methods=["DELETE"])
@catch_error
@jwt_auth
def delete_report_by_id(report_id: str):
    resp = HTTPResponse(request.method, request.path)
    report_ctrl.delete_report_by_id(request.ctx.user_id, report_id)
    return resp.return_with_log()


@report_routes.route("/<uuid:report_id>", methods=["PUT"])
@catch_error
@jwt_auth
def update_report_info(report_id: str):
    resp = HTTPResponse(request.method, request.path)
    req = report_ctrl.ReportUpdateInfo(**request.get_json())
    report_ctrl.update_report_info(request.ctx.user_id, report_id, req)
    return resp.return_with_log()


@report_routes.route("/<uuid:report_id>/batch-action", methods=["POST"])
@catch_error
@jwt_auth
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
                updates = {}
                if run_status.succeed_actions != last_info.succeed:
                    updates["succeed"] = run_status.succeed
                    last_info.succeed = run_status.succeed
                if run_status.failed_actions != last_info.failed:
                    updates["failed"] = run_status.failed
                    last_info.failed = run_status.failed
                if len(run_status.logs) != len(last_info.logs):
                    updates["logs"] = run_status.logs[len(last_info.logs):]
                    last_info.logs = run_status.logs

                if updates:
                    yield json.dumps(updates)

                if run_status.status == BatchActionRunStatus.Done:
                    break
        except GeneratorExit:
            logger.info("Client disconnected")


@report_routes.route("/<uuid:report_id>/batch-action-status", methods=["GET"])
@catch_error
@jwt_auth
def report_batch_action_status(report_id: str):
    batch_run = report_ctrl.get_latest_batch_action(request.ctx.user_id, report_id)

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
@jwt_auth
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
