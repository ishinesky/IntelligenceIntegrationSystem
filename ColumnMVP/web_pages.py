from __future__ import annotations

from typing import Callable, Optional

from flask import Blueprint, Flask, redirect, render_template, url_for


ViewDecorator = Callable[[Callable], Callable]


def create_column_admin_blueprint(
    *,
    login_required: Optional[ViewDecorator] = None,
    url_prefix: str = "",
) -> Blueprint:
    """Create page routes for managing OPC dynamic columns."""
    secure = login_required or (lambda fn: fn)
    bp = Blueprint("opc_column_pages", __name__, url_prefix=url_prefix)

    @bp.get("/opc-columns")
    @secure
    def opc_columns_index():
        return redirect(url_for("opc_column_pages.opc_column_admin"))

    @bp.get("/opc-columns/admin")
    @secure
    def opc_column_admin():
        return render_template("opc_column_admin.html")

    @bp.get("/opc-columns/source-quality")
    @secure
    def opc_source_quality():
        return render_template("opc_source_quality.html")

    @bp.get("/opc-columns/runtime-metrics")
    @secure
    def opc_runtime_metrics():
        return render_template("opc_runtime_metrics.html")

    @bp.get("/opc-columns/editorial-reviews")
    @secure
    def opc_editorial_reviews():
        return render_template("opc_editorial_reviews.html")

    @bp.get("/opc-columns/editorial-generation")
    @secure
    def opc_editorial_generation():
        return render_template("opc_editorial_generation.html")

    @bp.get("/opc-columns/article-lookup")
    @secure
    def opc_article_lookup():
        return render_template("opc_article_lookup.html")

    return bp


def register_column_admin_pages(
    app: Flask,
    *,
    login_required: Optional[ViewDecorator] = None,
    url_prefix: str = "",
) -> Blueprint:
    blueprint = create_column_admin_blueprint(
        login_required=login_required,
        url_prefix=url_prefix,
    )
    app.register_blueprint(blueprint)
    return blueprint
