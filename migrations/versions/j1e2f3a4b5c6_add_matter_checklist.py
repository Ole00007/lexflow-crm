"""add matter_checklist_items (Matter-stage checklist, WS-K)

Revision ID: j1e2f3a4b5c6
Revises: i0d1e2f3a4b5
Create Date: 2026-10-25

Additive only: one new tenant-scoped table (workspace_id NOT NULL, indexed).
New columns are nullable; the table carries workspace_id NOT NULL per the
multi-tenant rule. down_revision pinned to the current single head so
backend-dev can linearise wave-2 heads at merge.
"""
from alembic import op
import sqlalchemy as sa

revision = 'j1e2f3a4b5c6'
down_revision = 'i0d1e2f3a4b5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'matter_checklist_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('caseid', sa.Integer(), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('stage_key', sa.String(length=60), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('label', sa.String(length=200), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False, server_default='action'),
        sa.Column('required_doc', sa.String(length=200), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='todo'),
        sa.Column('blocked_reason', sa.String(length=300), nullable=True),
        sa.Column('owner_role', sa.String(length=30), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('vault_ref', sa.String(length=255), nullable=True),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tasks.id', ondelete='SET NULL'), nullable=True),
        sa.Column('completed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint('caseid', 'stage_key', 'position', name='uq_checklist_case_stage_pos'),
    )
    op.create_index('ix_matter_checklist_items_workspace_id', 'matter_checklist_items', ['workspace_id'])
    op.create_index('ix_matter_checklist_items_caseid', 'matter_checklist_items', ['caseid'])


def downgrade():
    op.drop_index('ix_matter_checklist_items_caseid', table_name='matter_checklist_items')
    op.drop_index('ix_matter_checklist_items_workspace_id', table_name='matter_checklist_items')
    op.drop_table('matter_checklist_items')
