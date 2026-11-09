"""add scheduled_actions table (T-009 delay engine)

Revision ID: l3a4b5c6d7e8
Revises: k2f3a4b5c6d7
Create Date: 2026-11-09 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'l3a4b5c6d7e8'
down_revision = 'k2f3a4b5c6d7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'scheduled_actions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=64), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=True),
        sa.Column('case_id', sa.Integer(), nullable=True),
        sa.Column('channel', sa.String(length=20), nullable=True),
        sa.Column('notif_type', sa.String(length=32), nullable=True),
        sa.Column('due_at', sa.DateTime(), nullable=False),
        sa.Column('state', sa.String(length=16), nullable=False, server_default='pending'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('suppression_key', sa.String(length=128), nullable=True),
        sa.Column('source', sa.String(length=16), nullable=False, server_default='rule'),
        sa.Column('payload', sa.Text(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('locked_at', sa.DateTime(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_scheduled_actions_workspace_id', 'scheduled_actions', ['workspace_id'])
    op.create_index('ix_scheduled_actions_contact_id', 'scheduled_actions', ['contact_id'])
    op.create_index('ix_scheduled_actions_case_id', 'scheduled_actions', ['case_id'])
    op.create_index('ix_scheduled_actions_suppression_key', 'scheduled_actions', ['suppression_key'])
    op.create_index('ix_scheduled_actions_state_due', 'scheduled_actions', ['state', 'due_at'])


def downgrade():
    op.drop_table('scheduled_actions')
