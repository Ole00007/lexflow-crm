"""notes provenance: source + source_ref (Mindmap human/agent attribution)

Revision ID: n6d7e8f9a0b1
Revises: m4a5b6c7d8e9
Create Date: 2026-11-18

Additive only. `notes` remains the human-written record; agent drafts live in
their own table and reach this one only through human promotion, which sets
source='agent' and source_ref=<draft id>.
"""
from alembic import op
import sqlalchemy as sa

revision = 'n6d7e8f9a0b1'
down_revision = 'm4a5b6c7d8e9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('notes') as batch:
        batch.add_column(sa.Column('source', sa.String(length=16), nullable=False, server_default='human'))
        batch.add_column(sa.Column('source_ref', sa.String(length=64), nullable=True))


def downgrade():
    with op.batch_alter_table('notes') as batch:
        batch.drop_column('source_ref')
        batch.drop_column('source')
