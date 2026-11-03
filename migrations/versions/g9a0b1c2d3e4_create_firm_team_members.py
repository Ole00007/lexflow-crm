"""create firm_team_members (was create_all-only; FK target of task_assignees / notify_consents)

Revision ID: g9a0b1c2d3e4
Revises: g8b9c0d1e2f3
Create Date: 2026-11-03

Additive, has_table-guarded (no-op on DBs where runtime create_all() already made it).
Inserted before h9c0d1e2f3a4 because that revision (and i0d1e2f3a4b5) FK to this table;
Postgres rejects the FK when the table is absent from the migration chain.
"""
from alembic import op
import sqlalchemy as sa

revision = 'g9a0b1c2d3e4'
down_revision = 'g8b9c0d1e2f3'
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table('firm_team_members'):
        return
    op.create_table(
        'firm_team_members',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_firm_team_members_workspace_id', 'firm_team_members', ['workspace_id'])


def downgrade():
    op.drop_table('firm_team_members')
