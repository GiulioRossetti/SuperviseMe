"""web links on user profiles

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    if "user_link" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "user_link",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_mgmt.id"), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("label", sa.String(100), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Integer(), nullable=False),
    )
    op.create_index("ix_user_link_user_id", "user_link", ["user_id"])


def downgrade():
    op.drop_table("user_link")
