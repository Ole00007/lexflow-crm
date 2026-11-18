"""merge heads: scheduled_actions/reconcile-drift + agent pending hash/expiry

Revision ID: n5c6d7e8f9a0
Revises: m4b5c6d7e8f9, m4a5b6c7d8e9
Create Date: 2026-11-18

Two migration branches diverged after k2f3a4b5c6d7:
  - lexflow_hermes_v1: l3a4b5c6d7e8 (scheduled_actions) -> m4b5c6d7e8f9 (reconcile drift)
  - feat/elisa-hardening: l3f4a5b6c7d8 (roi_progress) -> m4a5b6c7d8e9 (pending hash+expiry)
This revision only joins them; no DDL.
"""
from alembic import op  # noqa: F401

revision = 'n5c6d7e8f9a0'
down_revision = ('m4b5c6d7e8f9', 'm4a5b6c7d8e9')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
