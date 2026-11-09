"""thesis milestones, reminder log and email notification preferences

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    insp = inspect(op.get_bind())
    tables = set(insp.get_table_names())
    cols = {c["name"] for c in insp.get_columns("user_mgmt")}
    with op.batch_alter_table("user_mgmt", schema=None) as b:
        for name in ("email_notifications", "weekly_digest"):
            if name not in cols:
                b.add_column(sa.Column(name, sa.Boolean(), nullable=False, server_default="1"))
    if "thesis_milestone" not in tables:
        op.create_table(
            "thesis_milestone",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("thesis_id", sa.Integer(), sa.ForeignKey("thesis.id"), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("due_date", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("completed_at", sa.Integer(), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("user_mgmt.id"), nullable=True),
            sa.Column("created_at", sa.Integer(), nullable=False),
        )
        op.create_index("ix_thesis_milestone_thesis_id", "thesis_milestone", ["thesis_id"])
    if "reminder_log" not in tables:
        op.create_table(
            "reminder_log",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_mgmt.id"), nullable=False),
            sa.Column("kind", sa.String(40), nullable=False),
            sa.Column("ref_id", sa.Integer(), nullable=False),
            sa.Column("bucket", sa.String(30), nullable=False),
            sa.Column("sent_at", sa.Integer(), nullable=False),
            sa.UniqueConstraint("user_id", "kind", "ref_id", "bucket", name="uq_reminder_once"),
        )


def downgrade():
    op.drop_table("reminder_log")
    op.drop_index("ix_thesis_milestone_thesis_id", table_name="thesis_milestone")
    op.drop_table("thesis_milestone")
    with op.batch_alter_table("user_mgmt", schema=None) as b:
        b.drop_column("weekly_digest")
        b.drop_column("email_notifications")
