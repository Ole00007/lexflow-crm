"""add multitenant workspaces: workspace table + workspace_id on all data tables

Revision ID: 3a6b84c5d9f2
Revises: 2b5f63c3a9e1
Create Date: 2026-08-27 11:30:00.000000

Uses Alembic batch mode for SQLite compatibility.
"""
from alembic import op
import sqlalchemy as sa

revision = '3a6b84c5d9f2'
down_revision = '2b5f63c3a9e1'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create workspaces table
    op.create_table(
        'workspaces',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )

    # 2. Seed default workspace
    op.execute(
        "INSERT INTO workspaces (id, name, slug, description, is_active) "
        "VALUES (1, 'LexFlow Default', 'lexflow', 'Default workspace for legacy data', 1)"
    )

    # 3. Add workspace_id to each table using batch mode
    tables = [
        'users', 'contacts', 'cases', 'tasks', 'deadlines', 'notes',
        'activity_log', 'calendar_events', 'events',
    ]
    for table in tables:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column('workspace_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(f'fk_{table}_workspace', 'workspaces', ['workspace_id'], ['id'])
        op.execute(f"UPDATE {table} SET workspace_id = 1 WHERE workspace_id IS NULL")


def downgrade():
    tables = ['users', 'contacts', 'cases', 'tasks', 'deadlines', 'notes',
              'activity_log', 'calendar_events', 'events']
    for table in tables:
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(f'fk_{table}_workspace', type_='foreignkey')
            batch_op.drop_column('workspace_id')
    op.drop_table('workspaces')