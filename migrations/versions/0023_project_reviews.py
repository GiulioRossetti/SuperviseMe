"""internal review of project resources

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade():
    if "research_project_review" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "research_project_review",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("research_project.id"), nullable=False),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("research_project_resource.id"), nullable=False),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("user_mgmt.id"), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("user_mgmt.id"), nullable=False),
        sa.Column("note", sa.Text()), sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("comment", sa.Text()), sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False))
    op.create_index("ix_rp_review_project", "research_project_review", ["project_id"])
    op.create_index("ix_rp_review_reviewer", "research_project_review", ["reviewer_id"])


def downgrade():
    op.drop_table("research_project_review")
