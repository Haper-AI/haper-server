from flask import Blueprint, request

from biz.controller import report as report_ctrl
from biz.handler.middleware import catch_error, jwt_auth
from biz.utils.response import HTTPResponse

report_routes = Blueprint("report_api", __name__, url_prefix="/report")


# ---------------------- API routes ----------------------
@report_routes.route("/newest_summary", methods=["GET"])
@catch_error
@jwt_auth
def get_newest_report_summary():
    resp = HTTPResponse(request.method, request.path)
    report_summary = report_ctrl.get_newest_report_summary(request.ctx.user_id)

    resp.set_data({
        "summary": report_summary,
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
            "finished_at": latest_report.finished_at,
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
        "reports": [r.__dict__ for r in reports],
    })
    return resp.return_with_log()
