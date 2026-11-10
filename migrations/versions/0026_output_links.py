"""association of research output with users and theses

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade():
    if "research_output_link" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "research_output_link",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("output_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_mgmt.id")),
        sa.Column("thesis_id", sa.Integer(), sa.ForeignKey("thesis.id")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("user_mgmt.id")),
        sa.Column("created_at", sa.Integer(), nullable=False))
    op.create_index("ix_output_link_output", "research_output_link", ["kind", "output_id"])
    op.create_index("ix_research_output_link_user_id", "research_output_link", ["user_id"])
    op.create_index("ix_research_output_link_thesis_id", "research_output_link", ["thesis_id"])


def downgrade():
    op.drop_table("research_output_link")
