from flask import Blueprint, request

from biz.controller import report as report_ctrl
from biz.handler.middleware import catch_error, jwt_auth
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


@report_routes.route("/history", methods=["GET"])
@catch_error
@jwt_auth
def list_reports_history():
    resp = HTTPResponse(request.method, request.path)
    reports = report_ctrl.list_history_reports(request.ctx.user_id)
    resp.set_data({
        "reports": [{
            "id": str(r.id),
            "content": r.content,
            "created_at": r.created_at,
            "finalized_at": r.finalized_at,
        } for r in reports],
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