"""create notifications table

Revision ID: bf5e6a7b8c9d
Revises: ae4e5f6a7b8c
Create Date: 2026-08-27 12:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'bf5e6a7b8c9d'
down_revision = 'ae4e5f6a7b8c'

def upgrade():
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=True),
        sa.Column('user_to', sa.Integer(), nullable=True),
        sa.Column('user_from', sa.Integer(), nullable=True),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('reference_type', sa.String(20), nullable=True),
        sa.Column('reference_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('read', sa.Boolean(), nullable=False, server_default=sa.text("'0'")),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_to'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_from'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notifications_user_to', 'notifications', ['user_to'])
    op.create_index('ix_notifications_type', 'notifications', ['type'])

def downgrade():
    op.drop_index('ix_notifications_type', table_name='notifications')
    op.drop_index('ix_notifications_user_to', table_name='notifications')
    op.drop_table('notifications')