from __future__ import annotations

import json
import math
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_from_directory

import db

dashboard_bp = Blueprint("dashboard", __name__)

PAGE_SIZE = 50

FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"


@dashboard_bp.route("/api/requests")
def api_requests():
    pool = current_app.db_pool
    page = max(_to_int(request.args.get("page"), 1), 1)
    model = request.args.get("model") or None
    status = _to_int(request.args.get("status"), None)

    total = db.count_requests(pool, model=model, status=status)
    total_pages = max(math.ceil(total / PAGE_SIZE), 1)
    page = min(page, total_pages)
    rows = db.list_requests(pool, limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE, model=model, status=status)
    models = db.distinct_models(pool)

    return jsonify(
        {
            "rows": [_serialize_row(r) for r in rows],
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "models": models,
        }
    )


@dashboard_bp.route("/api/requests/<int:req_id>")
def api_request_detail(req_id):
    pool = current_app.db_pool
    row = db.get_request(pool, req_id)
    if row is None:
        return jsonify({"error": "not found"}), 404

    return jsonify(
        {
            "row": _serialize_row(row),
            "request_body": _pretty_json(row.get("request_body")),
            "response_body": _pretty_json(row.get("response_body")),
        }
    )


@dashboard_bp.route("/api/costs")
def api_costs():
    pool = current_app.db_pool
    summary = db.cost_summary(pool)
    by_model = db.cost_by_model(pool)
    over_time = db.cost_over_time(pool, days=14)

    return jsonify(
        {
            "summary": summary,
            "by_model": by_model,
            "series": {
                "labels": [r["day"].strftime("%Y-%m-%d") for r in over_time],
                "cost": [float(r["total_cost"]) for r in over_time],
                "count": [r["request_count"] for r in over_time],
            },
        }
    )


@dashboard_bp.route("/")
@dashboard_bp.route("/<path:subpath>")
def spa(subpath=""):
    if subpath:
        candidate = FRONTEND_DIST / subpath
        if candidate.is_file():
            return send_from_directory(FRONTEND_DIST, subpath)
    return send_from_directory(FRONTEND_DIST, "index.html")


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


def _serialize_row(row):
    out = dict(row)
    ts = out.get("timestamp_utc")
    if ts is not None:
        out["timestamp_utc"] = ts.isoformat()
    return out
