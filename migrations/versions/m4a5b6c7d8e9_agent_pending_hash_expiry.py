"""agent pending actions: payload_hash + expires_at (approval bound to exact content, with expiry)

Revision ID: m4a5b6c7d8e9
Revises: l3f4a5b6c7d8
Create Date: 2026-11-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'm4a5b6c7d8e9'
down_revision = 'l3f4a5b6c7d8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('agent_pending_actions', sa.Column('payload_hash', sa.String(length=64), nullable=True))
    op.add_column('agent_pending_actions', sa.Column('expires_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('agent_pending_actions', 'expires_at')
    op.drop_column('agent_pending_actions', 'payload_hash')
