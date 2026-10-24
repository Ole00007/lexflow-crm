"""add depends_on to tasks (Gantt dependency arrows)

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-10-24

Additive, nullable. Comma-separated task ids (same workspace), e.g. "12,15".
"""
from alembic import op
import sqlalchemy as sa

revision = 'g8b9c0d1e2f3'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.add_column(sa.Column('depends_on', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.drop_column('depends_on')
