"""research project images, tags, area, sub-projects and links

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    insp = inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("research_project")}
    with op.batch_alter_table("research_project", schema=None) as b:
        if "area" not in cols:
            b.add_column(sa.Column("area", sa.String(120), nullable=True))
        if "tags" not in cols:
            b.add_column(sa.Column("tags", sa.Text(), nullable=True))
        if "parent_id" not in cols:
            b.add_column(sa.Column("parent_id", sa.Integer(), nullable=True))
            b.create_foreign_key("fk_research_project_parent", "research_project", ["parent_id"], ["id"])
            b.create_index("ix_research_project_parent_id", ["parent_id"])
    tables = set(insp.get_table_names())
    if "research_project_image" not in tables:
        op.create_table(
            "research_project_image",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("research_project.id"), nullable=False),
            sa.Column("filename", sa.String(120), nullable=False, unique=True),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.Integer(), nullable=False),
        )
        op.create_index("ix_research_project_image_project_id", "research_project_image", ["project_id"])
    if "research_project_link" not in tables:
        op.create_table(
            "research_project_link",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("research_project.id"), nullable=False),
            sa.Column("linked_id", sa.Integer(), sa.ForeignKey("research_project.id"), nullable=False),
            sa.Column("relation", sa.String(30), nullable=False, server_default="related"),
            sa.Column("created_at", sa.Integer(), nullable=False),
            sa.UniqueConstraint("project_id", "linked_id", name="uq_research_project_link"),
        )
        op.create_index("ix_research_project_link_project_id", "research_project_link", ["project_id"])
        op.create_index("ix_research_project_link_linked_id", "research_project_link", ["linked_id"])


def downgrade():
    op.drop_table("research_project_link")
    op.drop_table("research_project_image")
    with op.batch_alter_table("research_project", schema=None) as b:
        b.drop_index("ix_research_project_parent_id")
        b.drop_constraint("fk_research_project_parent", type_="foreignkey")
        b.drop_column("parent_id")
        b.drop_column("tags")
        b.drop_column("area")
