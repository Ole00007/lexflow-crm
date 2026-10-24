"""add startdate to tasks

Revision ID: f7a8b9c0d1e2
Revises: e2f3a4b5c6d7
Create Date: 2026-10-14
"""
from alembic import op
import sqlalchemy as sa

revision = 'f7a8b9c0d1e2'
down_revision = 'e2f3a4b5c6d7'
branch_labels = None
depends_on = None


def upgrade():
    # Batch mode: portable across SQLite and Postgres.
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.add_column(sa.Column('startdate', sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.drop_column('startdate')
