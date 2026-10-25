"""Insights (WS-D) — Harvey-style usage/progress analytics.

- GET /insights            page shell (flag INSIGHTS_ENABLED else 404)
- GET /api/insights/summary?range=30|90|365   aggregates JSON (JWT, tenant-scoped)

AGGREGATES ONLY: no client names, task titles, emails, phone numbers or free
text. Flag off => both routes 404 and the nav link is hidden (kill-switch).
"""
import logging
import os

from flask import Blueprint, jsonify, render_template, request, abort
from flask_jwt_extended import jwt_required

from ..services.insights_aggregates import build_summary, VALID_RANGES

logger = logging.getLogger(__name__)

insights_bp = Blueprint('insights', __name__)


def _flag_on():
    return os.environ.get('INSIGHTS_ENABLED', 'false').strip().lower() in ('1', 'true', 'yes', 'on')


@insights_bp.get('/insights')
@jwt_required(optional=True)
def insights_page():
    """Page shell. Data + isolation come from /api/insights/summary (JWT)."""
    if not _flag_on():
        abort(404)
    return render_template('insights.html')


@insights_bp.get('/api/insights/summary')
@jwt_required()
def insights_summary():
    """Aggregates for the current user's visible workspaces."""
    if not _flag_on():
        abort(404)
    raw = request.args.get('range', '30')
    try:
        range_days = int(raw)
    except (TypeError, ValueError):
        return jsonify({'error': 'range must be 30, 90 or 365'}), 400
    if range_days not in VALID_RANGES:
        return jsonify({'error': 'range must be 30, 90 or 365'}), 400
    return jsonify(build_summary(range_days)), 200
