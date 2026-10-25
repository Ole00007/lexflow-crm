"""add agent audit tables

Revision ID: k2f3a4b5c6d7
Revises: i0d1e2f3a4b5
Create Date: 2026-10-25 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'k2f3a4b5c6d7'
down_revision = 'i0d1e2f3a4b5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'agent_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('goal', sa.String(length=500), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='running'),
        sa.Column('final_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.UniqueConstraint('run_id', name='uq_agent_runs_run_id'),
    )
    op.create_index(op.f('ix_agent_runs_workspace_id'), 'agent_runs', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_agent_runs_user_id'), 'agent_runs', ['user_id'], unique=False)
    op.create_index(op.f('ix_agent_runs_run_id'), 'agent_runs', ['run_id'], unique=False)

    op.create_table(
        'agent_audit',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('step_no', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('tool', sa.String(length=64), nullable=True),
        sa.Column('args_json', sa.Text(), nullable=True),
        sa.Column('result_summary', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index(op.f('ix_agent_audit_workspace_id'), 'agent_audit', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_agent_audit_user_id'), 'agent_audit', ['user_id'], unique=False)
    op.create_index(op.f('ix_agent_audit_run_id'), 'agent_audit', ['run_id'], unique=False)

    op.create_table(
        'agent_pending_actions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('tool', sa.String(length=64), nullable=False),
        sa.Column('args_json', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='pending'),
        sa.Column('decided_by', sa.Integer(), nullable=True),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('result_summary', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['decided_by'], ['users.id']),
    )
    op.create_index(op.f('ix_agent_pending_actions_workspace_id'), 'agent_pending_actions', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_agent_pending_actions_user_id'), 'agent_pending_actions', ['user_id'], unique=False)
    op.create_index(op.f('ix_agent_pending_actions_run_id'), 'agent_pending_actions', ['run_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_agent_pending_actions_run_id'), table_name='agent_pending_actions')
    op.drop_index(op.f('ix_agent_pending_actions_user_id'), table_name='agent_pending_actions')
    op.drop_index(op.f('ix_agent_pending_actions_workspace_id'), table_name='agent_pending_actions')
    op.drop_table('agent_pending_actions')

    op.drop_index(op.f('ix_agent_audit_run_id'), table_name='agent_audit')
    op.drop_index(op.f('ix_agent_audit_user_id'), table_name='agent_audit')
    op.drop_index(op.f('ix_agent_audit_workspace_id'), table_name='agent_audit')
    op.drop_table('agent_audit')

    op.drop_index(op.f('ix_agent_runs_run_id'), table_name='agent_runs')
    op.drop_index(op.f('ix_agent_runs_user_id'), table_name='agent_runs')
    op.drop_index(op.f('ix_agent_runs_workspace_id'), table_name='agent_runs')
    op.drop_table('agent_runs')
