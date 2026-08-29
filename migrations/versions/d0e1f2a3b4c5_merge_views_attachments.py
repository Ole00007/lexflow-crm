"""merge heads: saved views + attachments

Revision ID: d0e1f2a3b4c5
Revises: a1f2e3d4c5b6, c1d2e3f4a5b6
Create Date: 2026-08-29 23:05:00

"""
from alembic import op
import sqlalchemy as sa

revision = 'd0e1f2a3b4c5'
down_revision = ('a1f2e3d4c5b6', 'c1d2e3f4a5b6')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
