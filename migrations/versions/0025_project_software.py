"""software produced by research projects

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade():
    if "research_project_software" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "research_project_software",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("research_project.id"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("version", sa.String(50)), sa.Column("repo_url", sa.String(500)), sa.Column("doi", sa.String(200)),
        sa.Column("license", sa.String(100)), sa.Column("language", sa.String(100)), sa.Column("description", sa.String(500)),
        sa.Column("added_by", sa.Integer(), sa.ForeignKey("user_mgmt.id")),
        sa.Column("created_at", sa.Integer(), nullable=False))
    op.create_index("ix_rp_software_project", "research_project_software", ["project_id"])


def downgrade():
    op.drop_table("research_project_software")
