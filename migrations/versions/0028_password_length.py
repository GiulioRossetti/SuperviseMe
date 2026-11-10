"""widen user_mgmt.password (scrypt hashes are ~160 characters) and user_mgmt.cdl (degree course names)

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user_mgmt", schema=None) as batch_op:
        batch_op.alter_column("password", existing_type=sa.String(length=80), type_=sa.String(length=255), existing_nullable=False)
        batch_op.alter_column("cdl", existing_type=sa.String(length=15), type_=sa.String(length=120), existing_nullable=True)


def downgrade():
    with op.batch_alter_table("user_mgmt", schema=None) as batch_op:
        batch_op.alter_column("password", existing_type=sa.String(length=255), type_=sa.String(length=80), existing_nullable=False)
        batch_op.alter_column("cdl", existing_type=sa.String(length=120), type_=sa.String(length=15), existing_nullable=True)
