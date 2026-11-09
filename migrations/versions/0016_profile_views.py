"""profile view log

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    if "profile_view" not in inspect(op.get_bind()).get_table_names():
        op.create_table("profile_view",
                        sa.Column("id", sa.Integer(), primary_key=True),
                        sa.Column("viewer_id", sa.Integer(), sa.ForeignKey("user_mgmt.id"), nullable=False),
                        sa.Column("target_id", sa.Integer(), sa.ForeignKey("user_mgmt.id"), nullable=False),
                        sa.Column("viewed_at", sa.Integer(), nullable=False))
        op.create_index("ix_profile_view_viewer_id", "profile_view", ["viewer_id"])
        op.create_index("ix_profile_view_target_id", "profile_view", ["target_id"])


def downgrade():
    op.drop_table("profile_view")
