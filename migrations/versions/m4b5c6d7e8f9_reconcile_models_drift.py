"""reconcile model/migration drift: 2 tables + 5 columns never migrated

Revision ID: m4b5c6d7e8f9
Revises: l3a4b5c6d7e8
Create Date: 2026-11-11

Card t_fdbc90f7. Production DBs were built with db.create_all(), so these
objects exist there; a fresh DB built from the chain lacked them. Every step is
guarded (inspector) so the migration is a NO-OP on a DB that already has the
object and creates it on a fresh one. firm_team_members itself is created
(guarded) earlier, in h9c0d1e2f3a4, because FKs there need it.
"""
from alembic import context, op
import sqlalchemy as sa

revision = 'm4b5c6d7e8f9'
down_revision = 'l3a4b5c6d7e8'
branch_labels = None
depends_on = None


def _add_column(table, column):
    if context.is_offline_mode():
        cols = set()  # offline --sql: assume fresh DB
    else:
        cols = {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}
    if column.name not in cols:
        with op.batch_alter_table(table) as b:
            b.add_column(column)


def upgrade():
    offline = context.is_offline_mode()
    insp = None if offline else sa.inspect(op.get_bind())
    if offline or not insp.has_table('google_calendar_tokens'):
        op.create_table(
            'google_calendar_tokens',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('scope_key', sa.String(length=50), nullable=False, unique=True),
            sa.Column('refresh_token', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
    if offline or not insp.has_table('contact_relationships'):
        op.create_table(
            'contact_relationships',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('workspace_id', sa.Integer(), sa.ForeignKey('workspaces.id'), nullable=True),
            sa.Column('contact_id_a', sa.Integer(), sa.ForeignKey('contacts.id', ondelete='CASCADE'), nullable=False),
            sa.Column('contact_id_b', sa.Integer(), sa.ForeignKey('contacts.id', ondelete='CASCADE'), nullable=False),
            sa.Column('relationship_type', sa.String(length=100), nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('createdat', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updatedat', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )
    _add_column('workspaces', sa.Column('code_prefix', sa.String(length=5), nullable=True))
    _add_column('contacts', sa.Column('lifecycle_stage', sa.String(length=20), nullable=True))
    _add_column('contacts', sa.Column('tags', sa.Text(), nullable=True))
    _add_column('contacts', sa.Column('updated_at', sa.DateTime(), nullable=True))
    _add_column('cases', sa.Column('case_no', sa.String(length=20), nullable=True))


def downgrade():
    # Irreversible by design: on create_all-built DBs these objects pre-date this
    # revision, so dropping them would destroy data this revision did not create.
    pass
