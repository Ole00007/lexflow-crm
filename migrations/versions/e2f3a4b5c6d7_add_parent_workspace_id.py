"""add parent_workspace_id to workspaces

Revision ID: e2f3a4b5c6d7
Revises: d0e1f2a3b4c5
Create Date: 2026-08-30
"""
from alembic import op
import sqlalchemy as sa

revision = 'e2f3a4b5c6d7'
down_revision = 'd0e1f2a3b4c5'
branch_labels = None
depends_on = None


def upgrade():
    # Batch mode: portable across SQLite (needs copy-and-move) and Postgres.
    with op.batch_alter_table('workspaces') as batch_op:
        batch_op.add_column(sa.Column('parent_workspace_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_workspaces_parent', 'workspaces', ['parent_workspace_id'], ['id']
        )


def downgrade():
    with op.batch_alter_table('workspaces') as batch_op:
        batch_op.drop_constraint('fk_workspaces_parent', type_='foreignkey')
        batch_op.drop_column('parent_workspace_id')
