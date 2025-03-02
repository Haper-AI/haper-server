from typing import Optional, List, Dict
from uuid import UUID

from flask import Blueprint, request
from pydantic import BaseModel, field_validator

from biz.controller.report import (
    generate_new_report,
    get_newest_report_summary,
    list_history_reports,
)
from biz.handler.middleware import catch_error, jwt_auth
from biz.utils.response import HTTPResponse

report_routes = Blueprint("report_api", __name__, url_prefix="/api/v1/report")


class ReportResponse(BaseModel):
    report_id: UUID
    user_id: UUID
    content: Dict
    created_at: str

class GenerateReportRequest(BaseModel):
    filters: Optional[Dict] = None


# ---------------------- API routes ----------------------
@report_routes.route("/newest", methods=["GET"])
@catch_error
@jwt_auth
def get_newest_report():
    resp = HTTPResponse(request.method, request.path)
    report = get_newest_report_summary(request.ctx.user_id)
    resp.set_data(ReportResponse(**report.__dict__))
    return resp.return_with_log()

@report_routes.route("/generate", methods=["POST"])
@catch_error
@jwt_auth
def generate_report():
    resp = HTTPResponse(request.method, request.path)
    req = GenerateReportRequest(**request.get_json())
    new_report = generate_new_report(request.ctx.user_id, req.filters)
    resp.set_data(ReportResponse(**new_report.__dict__))
    return resp.return_with_log()

@report_routes.route("/history", methods=["GET"])
@catch_error
@jwt_auth
def list_reports_history():
    resp = HTTPResponse(request.method, request.path)
    reports = list_history_reports(request.ctx.user_id)
    resp.set_data([ReportResponse(**r.__dict__) for r in reports])
    return resp.return_with_log()
