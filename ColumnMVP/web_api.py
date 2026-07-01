from __future__ import annotations

import traceback
from typing import Callable, Optional

from flask import Blueprint, Flask, jsonify, request

from .column_service import ColumnService
from .column_store import ColumnStore


ViewDecorator = Callable[[Callable], Callable]


def _json_error(message: str, status_code: int = 400):
    return jsonify({"success": False, "error": message}), status_code


def create_column_blueprint(
    *,
    service: Optional[ColumnService] = None,
    login_required: Optional[ViewDecorator] = None,
    url_prefix: str = "/api/opc-columns",
) -> Blueprint:
    """Create a Flask blueprint for dynamic column management.

    Pass `WebServiceAccessManager.login_required` when registering inside the
    existing IntelligenceHub web service to keep these endpoints private.
    """
    column_service = service or ColumnService(ColumnStore())
    secure = login_required or (lambda fn: fn)
    bp = Blueprint("opc_columns", __name__, url_prefix=url_prefix)

    @bp.get("")
    @secure
    def list_columns():
        enabled_only = request.args.get("enabled_only", "false").lower() in {"1", "true", "yes", "on"}
        return jsonify({
            "success": True,
            "data": column_service.list_columns(enabled_only=enabled_only),
        })

    @bp.post("")
    @secure
    def create_column():
        try:
            payload = request.get_json(force=True) or {}
            overwrite = bool(payload.get("overwrite", False))
            validate_sources = bool(payload.get("validate_sources", True))
            column = column_service.create_column_from_payload(
                payload,
                overwrite=overwrite,
                validate_sources=validate_sources,
            )
            return jsonify({"success": True, "data": column.to_dict()}), 201
        except FileExistsError as exc:
            return _json_error(str(exc), 409)
        except ValueError as exc:
            return _json_error(str(exc), 400)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.post("/suggest-queries")
    @secure
    def suggest_queries():
        try:
            payload = request.get_json(force=True) or {}
            return jsonify({"success": True, "data": column_service.suggest_queries(payload)})
        except ValueError as exc:
            return _json_error(str(exc), 400)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.post("/discover-sources")
    @secure
    def discover_sources_from_topic():
        try:
            payload = request.get_json(force=True) or {}
            return jsonify({"success": True, "data": column_service.discover_sources_from_payload(payload)})
        except ValueError as exc:
            return _json_error(str(exc), 400)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.post("/validate-source")
    @secure
    def validate_source_url():
        try:
            payload = request.get_json(force=True) or {}
            url = str(payload.get("url", "")).strip()
            if not url:
                return _json_error("url is required", 400)
            return jsonify({"success": True, "data": column_service.validate_source_url(url)})
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.get("/editorial-reviews")
    @secure
    def list_editorial_reviews():
        try:
            payload = {
                "column_id": request.args.get("column_id", ""),
                "article_uuid": request.args.get("article_uuid", ""),
                "status": request.args.get("status", ""),
                "limit": request.args.get("limit", 50),
            }
            return jsonify({"success": True, "data": column_service.list_editorial_reviews(payload)})
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.post("/editorial-reviews")
    @secure
    def create_editorial_review():
        try:
            payload = request.get_json(force=True) or {}
            return jsonify({"success": True, "data": column_service.create_editorial_review(payload)}), 201
        except ValueError as exc:
            return _json_error(str(exc), 400)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.get("/editorial-reviews/<review_id>")
    @secure
    def get_editorial_review(review_id: str):
        try:
            return jsonify({"success": True, "data": column_service.get_editorial_review(review_id)})
        except FileNotFoundError:
            return _json_error("review not found", 404)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.get("/<column_id>")
    @secure
    def get_column(column_id: str):
        try:
            return jsonify({"success": True, "data": column_service.get_column(column_id).to_dict()})
        except FileNotFoundError:
            return _json_error("column not found", 404)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.patch("/<column_id>")
    @secure
    def update_column(column_id: str):
        try:
            payload = request.get_json(force=True) or {}
            column = column_service.update_column_metadata(column_id, payload)
            return jsonify({"success": True, "data": column.to_dict()})
        except FileNotFoundError:
            return _json_error("column not found", 404)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.post("/<column_id>/enable")
    @secure
    def enable_column(column_id: str):
        try:
            column = column_service.set_enabled(column_id, True)
            return jsonify({"success": True, "data": column.to_dict()})
        except FileNotFoundError:
            return _json_error("column not found", 404)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.post("/<column_id>/disable")
    @secure
    def disable_column(column_id: str):
        try:
            column = column_service.set_enabled(column_id, False)
            return jsonify({"success": True, "data": column.to_dict()})
        except FileNotFoundError:
            return _json_error("column not found", 404)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.post("/<column_id>/discover-sources")
    @secure
    def discover_sources_for_column(column_id: str):
        try:
            payload = request.get_json(force=True) or {}
            return jsonify({"success": True, "data": column_service.discover_sources_for_column(column_id, payload)})
        except FileNotFoundError:
            return _json_error("column not found", 404)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.post("/<column_id>/sources")
    @secure
    def add_sources(column_id: str):
        try:
            payload = request.get_json(force=True) or {}
            urls = payload.get("urls") or payload.get("url") or []
            if isinstance(urls, str):
                urls = [urls]
            validate_sources = bool(payload.get("validate_sources", True))
            column = column_service.add_sources(column_id, urls, validate_sources=validate_sources)
            return jsonify({"success": True, "data": column.to_dict()})
        except FileNotFoundError:
            return _json_error("column not found", 404)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.get("/<column_id>/source-quality")
    @secure
    def source_quality(column_id: str):
        try:
            live_validate = request.args.get("live_validate", "true").lower() in {"1", "true", "yes", "on"}
            return jsonify({"success": True, "data": column_service.audit_source_quality(
                column_id,
                live_validate=live_validate,
            )})
        except FileNotFoundError:
            return _json_error("column not found", 404)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.get("/<column_id>/source-runtime-metrics")
    @secure
    def source_runtime_metrics(column_id: str):
        try:
            return jsonify({"success": True, "data": column_service.get_source_runtime_metrics(column_id)})
        except FileNotFoundError:
            return _json_error("column not found", 404)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.post("/<column_id>/source-runtime-metrics")
    @secure
    def record_source_runtime_metric(column_id: str):
        try:
            payload = request.get_json(force=True) or {}
            return jsonify({"success": True, "data": column_service.record_source_runtime_metric(column_id, payload)}), 201
        except ValueError as exc:
            return _json_error(str(exc), 400)
        except FileNotFoundError:
            return _json_error("column not found", 404)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.get("/<column_id>/crawler-config")
    @secure
    def crawler_config_preview(column_id: str):
        try:
            return jsonify({"success": True, "data": column_service.get_crawler_config_preview(column_id)})
        except FileNotFoundError:
            return _json_error("column not found", 404)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    return bp


def register_column_routes(
    app: Flask,
    *,
    service: Optional[ColumnService] = None,
    login_required: Optional[ViewDecorator] = None,
    url_prefix: str = "/api/opc-columns",
) -> Blueprint:
    blueprint = create_column_blueprint(
        service=service,
        login_required=login_required,
        url_prefix=url_prefix,
    )
    app.register_blueprint(blueprint)
    return blueprint
