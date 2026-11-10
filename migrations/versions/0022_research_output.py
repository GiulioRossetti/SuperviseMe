"""research output: publications, funding, milestones, datasets, linked theses, public page

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def _fk(col, target):
    return sa.Column(col, sa.Integer(), sa.ForeignKey(target), nullable=False)


def upgrade():
    insp = inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("research_project")}
    new = [
        sa.Column("funder", sa.String(200), nullable=True),
        sa.Column("grant_id", sa.String(100), nullable=True),
        sa.Column("start_date", sa.String(10), nullable=True),
        sa.Column("end_date", sa.String(10), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("public_fields", sa.String(200), nullable=True),
    ]
    todo = [c for c in new if c.name not in cols]
    if todo:
        with op.batch_alter_table("research_project") as batch:
            for c in todo:
                batch.add_column(c)
    tables = set(insp.get_table_names())
    if "research_project_publication" not in tables:
        op.create_table(
            "research_project_publication",
            sa.Column("id", sa.Integer(), primary_key=True), _fk("project_id", "research_project.id"),
            sa.Column("title", sa.String(300), nullable=False), sa.Column("authors", sa.String(500)),
            sa.Column("year", sa.Integer()), sa.Column("venue", sa.String(300)), sa.Column("doi", sa.String(200)),
            sa.Column("url", sa.String(500)), sa.Column("pub_type", sa.String(30), nullable=False, server_default="article"),
            sa.Column("added_by", sa.Integer(), sa.ForeignKey("user_mgmt.id")), sa.Column("created_at", sa.Integer(), nullable=False))
        op.create_index("ix_rp_publication_project", "research_project_publication", ["project_id"])
    if "research_project_milestone" not in tables:
        op.create_table(
            "research_project_milestone",
            sa.Column("id", sa.Integer(), primary_key=True), _fk("project_id", "research_project.id"),
            sa.Column("title", sa.String(200), nullable=False), sa.Column("due_date", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.Integer(), nullable=False))
        op.create_index("ix_rp_milestone_project", "research_project_milestone", ["project_id"])
    if "research_project_dataset" not in tables:
        op.create_table(
            "research_project_dataset",
            sa.Column("id", sa.Integer(), primary_key=True), _fk("project_id", "research_project.id"),
            sa.Column("title", sa.String(300), nullable=False), sa.Column("doi", sa.String(200)),
            sa.Column("url", sa.String(500)), sa.Column("license", sa.String(100)), sa.Column("fair", sa.String(100)),
            sa.Column("created_at", sa.Integer(), nullable=False))
        op.create_index("ix_rp_dataset_project", "research_project_dataset", ["project_id"])
    if "research_project_thesis" not in tables:
        op.create_table(
            "research_project_thesis",
            sa.Column("id", sa.Integer(), primary_key=True), _fk("project_id", "research_project.id"),
            _fk("thesis_id", "thesis.id"), sa.Column("created_at", sa.Integer(), nullable=False),
            sa.UniqueConstraint("project_id", "thesis_id", name="uq_project_thesis"))
        op.create_index("ix_rp_thesis_project", "research_project_thesis", ["project_id"])
        op.create_index("ix_rp_thesis_thesis", "research_project_thesis", ["thesis_id"])


def downgrade():
    for t in ("research_project_thesis", "research_project_dataset", "research_project_milestone", "research_project_publication"):
        op.drop_table(t)
    with op.batch_alter_table("research_project") as batch:
        for c in ("public_fields", "is_public", "end_date", "start_date", "grant_id", "funder"):
            batch.drop_column(c)
