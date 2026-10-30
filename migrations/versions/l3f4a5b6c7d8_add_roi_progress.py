"""add roi_progress table

Revision ID: l3f4a5b6c7d8
Revises: k2f3a4b5c6d7
Create Date: 2026-10-30 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'l3f4a5b6c7d8'
down_revision = 'k2f3a4b5c6d7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'roi_progress',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('month', sa.String(length=7), nullable=False),
        sa.Column('hours_saved_actual', sa.Float(), nullable=False, server_default='0'),
        sa.Column('matters_handled', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.UniqueConstraint('workspace_id', 'user_id', 'month', name='uq_roi_progress_ws_user_month'),
    )
    op.create_index(op.f('ix_roi_progress_workspace_id'), 'roi_progress', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_roi_progress_user_id'), 'roi_progress', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_roi_progress_user_id'), table_name='roi_progress')
    op.drop_index(op.f('ix_roi_progress_workspace_id'), table_name='roi_progress')
    op.drop_table('roi_progress')
