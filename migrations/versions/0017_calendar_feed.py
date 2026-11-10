"""external calendar feed (iCal URL) for supervisors

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    if "calendar_feed" not in inspect(op.get_bind()).get_table_names():
        op.create_table("calendar_feed",
                        sa.Column("id", sa.Integer(), primary_key=True),
                        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_mgmt.id"), nullable=False, unique=True),
                        sa.Column("url_enc", sa.Text(), nullable=False),
                        sa.Column("busy_json", sa.Text(), nullable=True),
                        sa.Column("fetched_at", sa.Integer(), nullable=True),
                        sa.Column("last_attempt_at", sa.Integer(), nullable=True),
                        sa.Column("last_error", sa.String(200), nullable=True),
                        sa.Column("created_at", sa.Integer(), nullable=False))


def downgrade():
    op.drop_table("calendar_feed")
