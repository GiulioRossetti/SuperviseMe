"""add CheckConstraint on user_type column

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-09

Note: SQLite does not enforce CHECK constraints retroactively on existing rows,
but the constraint is recorded in the schema so new inserts/updates are
validated.  On PostgreSQL the USING clause handles existing data gracefully
because all existing user_type values are already within the allowed set.
"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None

_VALID_TYPES = "('admin', 'supervisor', 'student', 'researcher')"


def upgrade():
    with op.batch_alter_table('user_mgmt', schema=None) as batch_op:
        batch_op.create_check_constraint(
            'ck_user_mgmt_user_type',
            f"user_type IN {_VALID_TYPES}",
        )


def downgrade():
    with op.batch_alter_table('user_mgmt', schema=None) as batch_op:
        batch_op.drop_constraint('ck_user_mgmt_user_type', type_='check')
