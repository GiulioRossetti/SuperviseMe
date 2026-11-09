"""supervisor capacity, co-supervisor role and thesis reviewers

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    insp = inspect(op.get_bind())
    if "max_students" not in {c["name"] for c in insp.get_columns("user_mgmt")}:
        with op.batch_alter_table("user_mgmt", schema=None) as b:
            b.add_column(sa.Column("max_students", sa.Integer(), nullable=True))
    if "role" not in {c["name"] for c in insp.get_columns("thesis_supervisor")}:
        with op.batch_alter_table("thesis_supervisor", schema=None) as b:
            b.add_column(sa.Column("role", sa.String(20), nullable=False, server_default="supervisor"))
    if "thesis_reviewer" not in insp.get_table_names():
        op.create_table(
            "thesis_reviewer",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("thesis_id", sa.Integer(), sa.ForeignKey("thesis.id"), nullable=False),
            sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("user_mgmt.id"), nullable=False),
            sa.Column("assigned_by", sa.Integer(), sa.ForeignKey("user_mgmt.id"), nullable=True),
            sa.Column("assigned_at", sa.Integer(), nullable=False),
            sa.UniqueConstraint("thesis_id", "reviewer_id", name="uq_thesis_reviewer"),
        )
        op.create_index("ix_thesis_reviewer_thesis_id", "thesis_reviewer", ["thesis_id"])
        op.create_index("ix_thesis_reviewer_reviewer_id", "thesis_reviewer", ["reviewer_id"])


def downgrade():
    op.drop_table("thesis_reviewer")
    with op.batch_alter_table("thesis_supervisor", schema=None) as b:
        b.drop_column("role")
    with op.batch_alter_table("user_mgmt", schema=None) as b:
        b.drop_column("max_students")
