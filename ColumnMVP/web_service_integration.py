from __future__ import annotations

import logging
from typing import Any

from .web_api import register_column_routes
from .web_pages import register_column_admin_pages

logger = logging.getLogger(__name__)


def register_opc_column_routes(app: Any, login_required=None):
    """Register OPC column API and admin pages on an existing Flask app.

    This helper keeps the integration line small inside the large
    `IntelligenceHubWebService.register_routers` method.

    Example:

        from ColumnMVP.web_service_integration import register_opc_column_routes
        register_opc_column_routes(app, WebServiceAccessManager.login_required)

    Args:
        app: Existing Flask app instance.
        login_required: Optional route decorator. In IIS, pass
            `WebServiceAccessManager.login_required` so the column management
            API and page stay private.
    """
    api_blueprint = register_column_routes(
        app,
        login_required=login_required,
        url_prefix="/api/opc-columns",
    )
    page_blueprint = register_column_admin_pages(
        app,
        login_required=login_required,
        url_prefix="",
    )
    logger.info("OPC column API registered at /api/opc-columns")
    logger.info("OPC column admin page registered at /opc-columns/admin")
    return {
        "api": api_blueprint,
        "pages": page_blueprint,
    }


def patch_intelligence_hub_web_service() -> bool:
    """Monkey-patch IntelligenceHubWebService.register_routers.

    This is provided as an opt-in integration path for deployments that do not
    want to edit `IntelligenceHubWebService.py` directly. Prefer explicit
    registration in the web-service file when possible.

    Returns:
        True if the patch was installed or was already installed.
    """
    try:
        from IntelligenceHubWebService import IntelligenceHubWebService, WebServiceAccessManager
    except Exception as exc:
        logger.warning("Cannot import IntelligenceHubWebService for OPC column patch: %s", exc)
        return False

    original = getattr(IntelligenceHubWebService, "register_routers", None)
    if original is None:
        logger.warning("IntelligenceHubWebService.register_routers not found")
        return False

    if getattr(original, "_opc_column_patch_installed", False):
        return True

    def patched_register_routers(self, app):
        result = original(self, app)
        register_opc_column_routes(app, WebServiceAccessManager.login_required)
        return result

    patched_register_routers._opc_column_patch_installed = True
    patched_register_routers._opc_column_original = original
    IntelligenceHubWebService.register_routers = patched_register_routers
    logger.info("Installed OPC column routes monkey patch for IntelligenceHubWebService")
    return True
