from __future__ import annotations

import traceback
from typing import Callable, Optional

from flask import Blueprint, Flask, jsonify, request

from .publishing import EditorialPublishingService

ViewDecorator = Callable[[Callable], Callable]


def _json_error(message: str, status_code: int = 400):
    return jsonify({"success": False, "error": message}), status_code


def _payload() -> dict:
    return request.get_json(silent=True) or {}


def create_publishing_blueprint(
    *,
    service: Optional[EditorialPublishingService] = None,
    login_required: Optional[ViewDecorator] = None,
    url_prefix: str = "/api/opc-publishing",
) -> Blueprint:
    publishing_service = service or EditorialPublishingService()
    secure = login_required or (lambda fn: fn)
    bp = Blueprint("opc_publishing_api", __name__, url_prefix=url_prefix)

    @bp.post("/reviews/<review_id>/publish")
    @secure
    def publish_review(review_id: str):
        try:
            payload = _payload()
            return jsonify({"success": True, "data": publishing_service.publish(
                review_id,
                operator=str(payload.get("operator") or session_operator()),
                reason=str(payload.get("reason", "")),
            )})
        except FileNotFoundError:
            return _json_error("review not found", 404)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.post("/reviews/<review_id>/unpublish")
    @secure
    def unpublish_review(review_id: str):
        try:
            payload = _payload()
            return jsonify({"success": True, "data": publishing_service.unpublish(
                review_id,
                operator=str(payload.get("operator") or session_operator()),
                reason=str(payload.get("reason", "")),
            )})
        except FileNotFoundError:
            return _json_error("review not found", 404)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.post("/reviews/<review_id>/reject")
    @secure
    def reject_review(review_id: str):
        try:
            payload = _payload()
            return jsonify({"success": True, "data": publishing_service.reject(
                review_id,
                operator=str(payload.get("operator") or session_operator()),
                reason=str(payload.get("reason", "")),
            )})
        except FileNotFoundError:
            return _json_error("review not found", 404)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.post("/reviews/<review_id>/status")
    @secure
    def set_review_status(review_id: str):
        try:
            payload = _payload()
            return jsonify({"success": True, "data": publishing_service.set_status(
                review_id,
                str(payload.get("status", "")),
                operator=str(payload.get("operator") or session_operator()),
                reason=str(payload.get("reason", "")),
                metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
            )})
        except ValueError as exc:
            return _json_error(str(exc), 400)
        except FileNotFoundError:
            return _json_error("review not found", 404)
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.get("/reviews/<review_id>/audit")
    @secure
    def review_audit(review_id: str):
        try:
            limit = int(request.args.get("limit", 100))
            return jsonify({"success": True, "data": publishing_service.audit(review_id=review_id, limit=limit)})
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    @bp.get("/audit")
    @secure
    def all_audit():
        try:
            limit = int(request.args.get("limit", 100))
            review_id = request.args.get("review_id", "")
            return jsonify({"success": True, "data": publishing_service.audit(review_id=review_id, limit=limit)})
        except Exception as exc:
            traceback.print_exc()
            return _json_error(str(exc), 500)

    return bp


def session_operator() -> str:
    try:
        from flask import session
        return session.get("username") or str(session.get("user_id") or "system")
    except Exception:
        return "system"


def register_publishing_api(
    app: Flask,
    *,
    service: Optional[EditorialPublishingService] = None,
    login_required: Optional[ViewDecorator] = None,
    url_prefix: str = "/api/opc-publishing",
) -> Blueprint:
    blueprint = create_publishing_blueprint(
        service=service,
        login_required=login_required,
        url_prefix=url_prefix,
    )
    app.register_blueprint(blueprint)
    return blueprint
