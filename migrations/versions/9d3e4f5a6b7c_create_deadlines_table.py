"""create deadlines table

Revision ID: 9d3e4f5a6b7c
Revises: 8c2d3e4f5a6b
Create Date: 2026-06-19 02:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '9d3e4f5a6b7c'
down_revision = '8c2d3e4f5a6b'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'deadlines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('caseid', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('deadline_date', sa.Date(), nullable=False),
        sa.Column('deadline_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('priority', sa.String(length=20), nullable=False, server_default='Medium'),
        sa.Column('createdat', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updatedat', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['caseid'], ['cases.id'], name=op.f('deadlines_caseid_fkey'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_deadlines_caseid'), 'deadlines', ['caseid'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_deadlines_caseid'), table_name='deadlines')
    op.drop_table('deadlines')
