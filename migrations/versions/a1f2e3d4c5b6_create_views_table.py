"""create views table (saved views / viste salvate)

Revision ID: a1f2e3d4c5b6
Revises: bf5e6a7b8c9d
Create Date: 2026-08-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1f2e3d4c5b6'
down_revision = 'bf5e6a7b8c9d'


def upgrade():
    op.create_table(
        'views',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('object_type', sa.String(50), nullable=False),
        sa.Column('filters_json', sa.JSON(), nullable=True),
        sa.Column('sort_json', sa.JSON(), nullable=True),
        sa.Column('visible_columns_json', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.text("'0'")),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_views_workspace_id', 'views', ['workspace_id'])
    op.create_index('ix_views_object_type', 'views', ['object_type'])
    op.create_index('ix_views_created_by', 'views', ['created_by'])


def downgrade():
    op.drop_index('ix_views_created_by', table_name='views')
    op.drop_index('ix_views_object_type', table_name='views')
    op.drop_index('ix_views_workspace_id', table_name='views')
    op.drop_table('views')
