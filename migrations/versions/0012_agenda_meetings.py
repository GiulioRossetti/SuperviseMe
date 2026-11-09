"""availability slots and meetings

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    tables = set(inspect(op.get_bind()).get_table_names())
    if "availability_slot" not in tables:
        op.create_table(
            "availability_slot",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("supervisor_id", sa.Integer(), sa.ForeignKey("user_mgmt.id"), nullable=False),
            sa.Column("start_ts", sa.Integer(), nullable=False),
            sa.Column("end_ts", sa.Integer(), nullable=False),
            sa.Column("location", sa.String(200), nullable=True),
            sa.Column("booked_by", sa.Integer(), sa.ForeignKey("user_mgmt.id"), nullable=True),
            sa.Column("created_at", sa.Integer(), nullable=False),
        )
        op.create_index("ix_availability_slot_supervisor_id", "availability_slot", ["supervisor_id"])
    if "meeting" not in tables:
        op.create_table(
            "meeting",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("thesis_id", sa.Integer(), sa.ForeignKey("thesis.id"), nullable=False),
            sa.Column("supervisor_id", sa.Integer(), sa.ForeignKey("user_mgmt.id"), nullable=False),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("user_mgmt.id"), nullable=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("start_ts", sa.Integer(), nullable=False),
            sa.Column("end_ts", sa.Integer(), nullable=False),
            sa.Column("location", sa.String(200), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
            sa.Column("slot_id", sa.Integer(), sa.ForeignKey("availability_slot.id"), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("user_mgmt.id"), nullable=True),
            sa.Column("created_at", sa.Integer(), nullable=False),
        )
        op.create_index("ix_meeting_thesis_id", "meeting", ["thesis_id"])


def downgrade():
    op.drop_index("ix_meeting_thesis_id", table_name="meeting")
    op.drop_table("meeting")
    op.drop_index("ix_availability_slot_supervisor_id", table_name="availability_slot")
    op.drop_table("availability_slot")
