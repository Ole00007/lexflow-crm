"""add gdpr fields + source to contacts

Revision ID: ae4e5f6a7b8c
Revises: 3a6b84c5d9f2
Create Date: 2026-08-27 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'ae4e5f6a7b8c'
down_revision = '3a6b84c5d9f2'

def upgrade():
    with op.batch_alter_table('contacts') as batch_op:
        batch_op.add_column(sa.Column('source', sa.String(20), nullable=False, server_default='manual'))
        batch_op.add_column(sa.Column('gdpr_consent', sa.Boolean(), nullable=False, server_default=sa.text("'0'")))
        batch_op.add_column(sa.Column('gdpr_consent_ts', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))
        batch_op.alter_column('email', existing_type=sa.String(255), nullable=False)

def downgrade():
    with op.batch_alter_table('contacts') as batch_op:
        batch_op.drop_column('created_at')
        batch_op.drop_column('gdpr_consent_ts')
        batch_op.drop_column('gdpr_consent')
        batch_op.drop_column('source')
        batch_op.alter_column('email', existing_type=sa.String(255), nullable=True)