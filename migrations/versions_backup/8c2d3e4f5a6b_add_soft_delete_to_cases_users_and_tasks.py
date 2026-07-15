"""add soft delete to cases users and tasks

Revision ID: 8c2d3e4f5a6b
Revises: 7a8b9c0d1e2f
Create Date: 2026-06-19 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '8c2d3e4f5a6b'
down_revision = '7a8b9c0d1e2f'
branch_labels = None
depends_on = None


def upgrade():
    # Add soft delete columns to cases table
    op.add_column('cases', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('cases', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    
    # Add soft delete columns to users table
    op.add_column('users', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    
    # Add soft delete columns to tasks table
    op.add_column('tasks', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('tasks', sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade():
    # Remove soft delete columns from tasks table
    op.drop_column('tasks', 'deleted_at')
    op.drop_column('tasks', 'is_deleted')
    
    # Remove soft delete columns from users table
    op.drop_column('users', 'deleted_at')
    op.drop_column('users', 'is_deleted')
    
    # Remove soft delete columns from cases table
    op.drop_column('cases', 'deleted_at')
    op.drop_column('cases', 'is_deleted')
