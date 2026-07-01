from __future__ import annotations

import traceback
from typing import Callable, Optional

from flask import Blueprint, Flask, Response, jsonify, request

from .column_service import ColumnService
from .column_store import ColumnStore


ViewDecorator = Callable[[Callable], Callable]


def _json_error(message: str, status_code: int = 400):
    return jsonify({"success": False, "error": message}), status_code


def create_opc_resource_blueprint(
    *,
    service: Optional[ColumnService] = None,
    login_required: Optional[ViewDecorator] = None,
    url_prefix: str = "/api/opc-resource",
) -> Blueprint:
    column_service = service or ColumnService(ColumnStore())
    secure = login_required or (lambda fn: fn)
    bp = Blueprint("opc_resource_api", __name__, url_prefix=url_prefix)

    @bp.get("/columns")
    @secure
    def resource_columns():
        try:
            include_disabled = request.args.get("include_disabled", "false").lower() in {"1", "true", "yes", "on"}
            return jsonify({"success": True, "data": column_service.public_columns(include_disabled=include_disabled)})
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.get("/columns/<column_id>")
    @secure
    def resource_column_detail(column_id: str):
        try:
            return jsonify({"success": True, "data": column_service.public_column_detail(column_id)})
        except FileNotFoundError:
            return _json_error("column not found", 404)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.get("/feed")
    @secure
    def resource_feed():
        try:
            payload = {
                "column_id": request.args.get("column_id", ""),
                "keyword": request.args.get("keyword", ""),
                "status": request.args.get("status", "published"),
                "min_quality": request.args.get("min_quality", 0),
                "min_actionability": request.args.get("min_actionability", 0),
                "limit": request.args.get("limit", 50),
            }
            return jsonify({"success": True, "data": column_service.public_feed(payload)})
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.get("/reviews/<review_id>")
    @secure
    def resource_review_detail(review_id: str):
        try:
            return jsonify({"success": True, "data": column_service.public_review_detail(review_id)})
        except FileNotFoundError:
            return _json_error("review not found", 404)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.get("/rss.xml")
    @secure
    def resource_rss():
        try:
            payload = {
                "base_url": request.url_root.rstrip("/"),
                "column_id": request.args.get("column_id", ""),
                "keyword": request.args.get("keyword", ""),
                "limit": request.args.get("limit", 30),
                "title": request.args.get("title", "OPC Resource Feed"),
            }
            xml = column_service.public_rss(payload)
            return Response(xml, content_type="application/rss+xml; charset=utf-8")
        except Exception as exc:
            traceback.print_exc()
            return Response(str(exc), status=500, content_type="text/plain; charset=utf-8")

    return bp


def register_opc_resource_api(
    app: Flask,
    *,
    service: Optional[ColumnService] = None,
    login_required: Optional[ViewDecorator] = None,
    url_prefix: str = "/api/opc-resource",
) -> Blueprint:
    blueprint = create_opc_resource_blueprint(
        service=service,
        login_required=login_required,
        url_prefix=url_prefix,
    )
    app.register_blueprint(blueprint)
    return blueprint
