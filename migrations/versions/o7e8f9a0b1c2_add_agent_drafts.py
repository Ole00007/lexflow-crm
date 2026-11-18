"""agent drafts sandbox: agent_policies, agent_drafts, agent_delegations

Revision ID: o7e8f9a0b1c2
Revises: n6d7e8f9a0b1
Create Date: 2026-11-18

Additive only (three new tables, no ALTER of existing ones). Agents write only
to agent_drafts; a human accept promotes a draft into notes (source='agent').
"""
from alembic import op
import sqlalchemy as sa

revision = 'o7e8f9a0b1c2'
down_revision = 'n6d7e8f9a0b1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'agent_policies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('event_key', sa.String(length=64), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('require_review', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('max_per_day', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('workspace_id', 'event_key', name='uq_agent_policy_ws_event'),
    )
    with op.batch_alter_table('agent_policies') as batch:
        batch.create_index('ix_agent_policies_workspace_id', ['workspace_id'])

    op.create_table(
        'agent_drafts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('origin', sa.String(length=20), nullable=False),
        sa.Column('requested_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('requested_by_agent', sa.String(length=64), nullable=True),
        sa.Column('evidence', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('policy_id', sa.Integer(), sa.ForeignKey('agent_policies.id'), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('decided_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('note_id', sa.Integer(), sa.ForeignKey('notes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    with op.batch_alter_table('agent_drafts') as batch:
        batch.create_index('ix_agent_drafts_workspace_id', ['workspace_id'])
        batch.create_index('ix_agent_drafts_target', ['workspace_id', 'target_type', 'target_id'])

    op.create_table(
        'agent_delegations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('from_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('to_agent', sa.String(length=64), nullable=False),
        sa.Column('scope', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    with op.batch_alter_table('agent_delegations') as batch:
        batch.create_index('ix_agent_delegations_workspace_id', ['workspace_id'])


def downgrade():
    op.drop_table('agent_delegations')
    op.drop_table('agent_drafts')
    op.drop_table('agent_policies')
