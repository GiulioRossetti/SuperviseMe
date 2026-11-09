"""widen name and surname columns from String(15) to String(50)

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-09

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user_mgmt', schema=None) as batch_op:
        batch_op.alter_column(
            'name',
            existing_type=sa.String(length=15),
            type_=sa.String(length=50),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'surname',
            existing_type=sa.String(length=15),
            type_=sa.String(length=50),
            existing_nullable=True,
        )


def downgrade():
    with op.batch_alter_table('user_mgmt', schema=None) as batch_op:
        batch_op.alter_column(
            'surname',
            existing_type=sa.String(length=50),
            type_=sa.String(length=15),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'name',
            existing_type=sa.String(length=50),
            type_=sa.String(length=15),
            existing_nullable=True,
        )
