"""end-of-thesis checklist

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    insp = inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("thesis")}
    with op.batch_alter_table("thesis", schema=None) as b:
        if "defense_date" not in cols:
            b.add_column(sa.Column("defense_date", sa.Integer(), nullable=True))
        if "degree_course" not in cols:
            b.add_column(sa.Column("degree_course", sa.String(120), nullable=True))
    tables = insp.get_table_names()
    if "checklist_template" not in tables:
        op.create_table("checklist_template",
                        sa.Column("id", sa.Integer(), primary_key=True),
                        sa.Column("name", sa.String(150), nullable=False),
                        sa.Column("degree_course", sa.String(120), nullable=True),
                        sa.Column("created_at", sa.Integer(), nullable=False))
    if "checklist_template_item" not in tables:
        op.create_table("checklist_template_item",
                        sa.Column("id", sa.Integer(), primary_key=True),
                        sa.Column("template_id", sa.Integer(), sa.ForeignKey("checklist_template.id"), nullable=False),
                        sa.Column("title", sa.String(200), nullable=False),
                        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
                        sa.Column("days_before_defense", sa.Integer(), nullable=True))
        op.create_index("ix_checklist_template_item_template_id", "checklist_template_item", ["template_id"])
    if "thesis_checklist_item" not in tables:
        op.create_table("thesis_checklist_item",
                        sa.Column("id", sa.Integer(), primary_key=True),
                        sa.Column("thesis_id", sa.Integer(), sa.ForeignKey("thesis.id"), nullable=False),
                        sa.Column("title", sa.String(200), nullable=False),
                        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
                        sa.Column("days_before_defense", sa.Integer(), nullable=True),
                        sa.Column("due_date", sa.Integer(), nullable=True),
                        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
                        sa.Column("completed_at", sa.Integer(), nullable=True),
                        sa.Column("completed_by", sa.Integer(), sa.ForeignKey("user_mgmt.id"), nullable=True),
                        sa.Column("created_at", sa.Integer(), nullable=False))
        op.create_index("ix_thesis_checklist_item_thesis_id", "thesis_checklist_item", ["thesis_id"])


def downgrade():
    op.drop_table("thesis_checklist_item")
    op.drop_table("checklist_template_item")
    op.drop_table("checklist_template")
    with op.batch_alter_table("thesis", schema=None) as b:
        b.drop_column("degree_course")
        b.drop_column("defense_date")
