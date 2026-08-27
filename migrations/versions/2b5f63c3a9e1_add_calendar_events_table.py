"""add calendar_events table for legal event management

Revision ID: 2b5f63c3a9e1
Revises: 9a4b63c29d1e
Create Date: 2026-08-24 10:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '2b5f63c3a9e1'
down_revision = '9a4b63c29d1e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'calendar_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('caseid', sa.Integer(), nullable=True),
        sa.Column('contactid', sa.Integer(), nullable=True),
        sa.Column('ownerid', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('event_type', sa.String(50), nullable=False, server_default='hearing'),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('court_name', sa.String(255), nullable=True),
        sa.Column('judge_name', sa.String(255), nullable=True),
        sa.Column('start_datetime', sa.DateTime(), nullable=False),
        sa.Column('end_datetime', sa.DateTime(), nullable=True),
        sa.Column('is_all_day', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(50), nullable=False, server_default='scheduled'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('createdat', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updatedat', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['caseid'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contactid'], ['contacts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['ownerid'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_calendar_start', 'calendar_events', ['start_datetime'])
    op.create_index('ix_calendar_case', 'calendar_events', ['caseid'])
    op.create_index('ix_calendar_type', 'calendar_events', ['event_type'])


def downgrade():
    op.drop_table('calendar_events')