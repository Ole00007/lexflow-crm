"""create attachments table

Revision ID: c1d2e3f4a5b6
Revises: bf5e6a7b8c9d
Create Date: 2026-08-29 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c1d2e3f4a5b6'
down_revision = 'bf5e6a7b8c9d'


def upgrade():
    op.create_table(
        'attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('stored_name', sa.String(255), nullable=False),
        sa.Column('filepath', sa.String(500), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('target_type', sa.String(50), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('uploaded_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_attachments_stored_name', 'attachments', ['stored_name'], unique=True)
    op.create_index('ix_attachments_target', 'attachments', ['target_type', 'target_id'])


def downgrade():
    op.drop_index('ix_attachments_target', table_name='attachments')
    op.drop_index('ix_attachments_stored_name', table_name='attachments')
    op.drop_table('attachments')
