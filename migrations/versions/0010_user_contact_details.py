"""add office_location, phone and contact_email to user_mgmt

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

COLUMNS = [("office_location", 120), ("phone", 40), ("contact_email", 120)]


def upgrade():
    existing = {c["name"] for c in inspect(op.get_bind()).get_columns("user_mgmt")}
    with op.batch_alter_table("user_mgmt", schema=None) as batch_op:
        for name, length in COLUMNS:
            if name not in existing:
                batch_op.add_column(sa.Column(name, sa.String(length=length), nullable=True))


def downgrade():
    with op.batch_alter_table("user_mgmt", schema=None) as batch_op:
        for name, _ in COLUMNS:
            batch_op.drop_column(name)
