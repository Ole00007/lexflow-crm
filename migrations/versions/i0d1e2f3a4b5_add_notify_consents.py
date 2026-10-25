"""add notify_consents (opt-in records for Telegram/WhatsApp notifications)

Revision ID: i0d1e2f3a4b5
Revises: h9c0d1e2f3a4
Create Date: 2026-10-25

Additive only: one new tenant-scoped table (workspace_id NOT NULL).
"""
from alembic import op
import sqlalchemy as sa

revision = 'i0d1e2f3a4b5'
down_revision = 'h9c0d1e2f3a4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'notify_consents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('firm_team_members.id', ondelete='CASCADE'), nullable=False),
        sa.Column('channel', sa.String(length=20), nullable=False),
        sa.Column('granted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('telegram_chat_id', sa.String(length=64), nullable=True),
        sa.Column('consented_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('consented_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('member_id', 'channel', name='uq_notify_consent_member_channel'),
    )
    op.create_index('ix_notify_consents_workspace_id', 'notify_consents', ['workspace_id'])
    op.create_index('ix_notify_consents_member_id', 'notify_consents', ['member_id'])


def downgrade():
    op.drop_table('notify_consents')
