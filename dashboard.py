from __future__ import annotations

import json
import math

from flask import Blueprint, abort, current_app, render_template, request

import db

dashboard_bp = Blueprint("dashboard", __name__)

PAGE_SIZE = 50


@dashboard_bp.route("/requests")
def requests_view():
    pool = current_app.db_pool
    page = max(_to_int(request.args.get("page"), 1), 1)
    model = request.args.get("model") or None
    status_raw = request.args.get("status") or None
    status = _to_int(status_raw, None)

    total = db.count_requests(pool, model=model, status=status)
    total_pages = max(math.ceil(total / PAGE_SIZE), 1)
    page = min(page, total_pages)
    rows = db.list_requests(pool, limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE, model=model, status=status)
    models = db.distinct_models(pool)

    return render_template(
        "requests.html",
        rows=rows,
        page=page,
        total_pages=total_pages,
        total=total,
        models=models,
        selected_model=model or "",
        selected_status=status_raw or "",
    )


@dashboard_bp.route("/requests/<int:req_id>")
def request_detail(req_id):
    pool = current_app.db_pool
    row = db.get_request(pool, req_id)
    if row is None:
        abort(404)

    return render_template(
        "request_detail.html",
        row=row,
        request_body=_pretty_json(row.get("request_body")),
        response_body=_pretty_json(row.get("response_body")),
    )


@dashboard_bp.route("/costs")
def costs_view():
    pool = current_app.db_pool
    summary = db.cost_summary(pool)
    by_model = db.cost_by_model(pool)
    over_time = db.cost_over_time(pool, days=14)

    return render_template(
        "costs.html",
        summary=summary,
        by_model=by_model,
        labels=json.dumps([r["day"].strftime("%Y-%m-%d") for r in over_time]),
        cost_series=json.dumps([float(r["total_cost"]) for r in over_time]),
        count_series=json.dumps([r["request_count"] for r in over_time]),
    )


def _to_int(value, default):
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _pretty_json(raw):
    if not raw:
        return None
    try:
        return json.dumps(json.loads(raw), indent=2)
    except (TypeError, json.JSONDecodeError):
        return raw
