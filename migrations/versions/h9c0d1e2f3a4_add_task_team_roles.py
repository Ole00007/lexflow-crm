"""add task team roles, lawyer flags and tasks.vault_ref (Gantt WS-A)

Revision ID: h9c0d1e2f3a4
Revises: g8b9c0d1e2f3
Create Date: 2026-10-24

Additive only: two new tables + one nullable column.
"""
from alembic import op
import sqlalchemy as sa

revision = 'h9c0d1e2f3a4'
down_revision = 'g8b9c0d1e2f3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.add_column(sa.Column('vault_ref', sa.String(length=255), nullable=True))
    op.create_table(
        'task_assignees',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('team_member_id', sa.Integer(), sa.ForeignKey('firm_team_members.id'), nullable=False),
        sa.Column('role', sa.String(length=30), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('task_id', 'team_member_id', 'role', name='uq_task_assignee_role'),
    )
    op.create_index('ix_task_assignees_workspace_id', 'task_assignees', ['workspace_id'])
    op.create_index('ix_task_assignees_task_id', 'task_assignees', ['task_id'])
    op.create_index('ix_task_assignees_team_member_id', 'task_assignees', ['team_member_id'])
    op.create_table(
        'task_flags',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('raised_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('raised_by_agent', sa.String(length=80), nullable=True),
        sa.Column('target_member_id', sa.Integer(), sa.ForeignKey('firm_team_members.id'), nullable=True),
        sa.Column('reason', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='open'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_task_flags_workspace_id', 'task_flags', ['workspace_id'])
    op.create_index('ix_task_flags_task_id', 'task_flags', ['task_id'])


def downgrade():
    op.drop_table('task_flags')
    op.drop_table('task_assignees')
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.drop_column('vault_ref')
