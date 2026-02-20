"""add orcid support

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-19 12:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    # Helper to check if column exists
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = [c['name'] for c in inspector.get_columns('user_mgmt')]

    with op.batch_alter_table('user_mgmt', schema=None) as batch_op:
        if 'google_id' not in columns:
            batch_op.add_column(sa.Column('google_id', sa.String(length=100), nullable=True))
            batch_op.create_unique_constraint(batch_op.f('uq_user_mgmt_google_id'), ['google_id'])

        if 'orcid_id' not in columns:
            batch_op.add_column(sa.Column('orcid_id', sa.String(length=20), nullable=True))
            batch_op.create_unique_constraint(batch_op.f('uq_user_mgmt_orcid_id'), ['orcid_id'])

        if 'orcid_access_token' not in columns:
            batch_op.add_column(sa.Column('orcid_access_token', sa.String(length=255), nullable=True))

        if 'orcid_refresh_token' not in columns:
            batch_op.add_column(sa.Column('orcid_refresh_token', sa.String(length=255), nullable=True))

    # Create OrcidActivity table
    tables = inspector.get_table_names()
    if 'orcid_activity' not in tables:
        op.create_table(
            'orcid_activity',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(length=500), nullable=False),
            sa.Column('type', sa.String(length=50), nullable=False),
            sa.Column('organization', sa.String(length=255), nullable=True),
            sa.Column('publication_date', sa.String(length=20), nullable=True),
            sa.Column('url', sa.String(length=500), nullable=True),
            sa.Column('external_ids', sa.Text(), nullable=True),
            sa.Column('created_at', sa.Integer(), nullable=False),
            sa.Column('updated_at', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user_mgmt.id'], name=op.f('fk_orcid_activity_user_id_user_mgmt')),
            sa.PrimaryKeyConstraint('id', name=op.f('pk_orcid_activity'))
        )


def downgrade():
    op.drop_table('orcid_activity')

    # Only drop if they exist to avoid errors on downgrade
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = [c['name'] for c in inspector.get_columns('user_mgmt')]

    with op.batch_alter_table('user_mgmt', schema=None) as batch_op:
        if 'orcid_refresh_token' in columns:
            batch_op.drop_column('orcid_refresh_token')
        if 'orcid_access_token' in columns:
            batch_op.drop_column('orcid_access_token')

        if 'orcid_id' in columns:
            batch_op.drop_constraint(batch_op.f('uq_user_mgmt_orcid_id'), type_='unique')
            batch_op.drop_column('orcid_id')

        if 'google_id' in columns:
            batch_op.drop_constraint(batch_op.f('uq_user_mgmt_google_id'), type_='unique')
            batch_op.drop_column('google_id')
