"""create users table before cases references it

Revision ID: 66c943d77b4e
Revises: 65b843c76b3d
Create Date: 2026-06-18 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '66c943d77b4e'
down_revision = '65b843c76b3d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )


def downgrade():
    op.drop_table('users')
