"""thesis documents with versions and comments

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    tables = set(inspect(op.get_bind()).get_table_names())
    if "thesis_document" not in tables:
        op.create_table(
            "thesis_document",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("thesis_id", sa.Integer(), sa.ForeignKey("thesis.id"), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("user_mgmt.id"), nullable=True),
            sa.Column("created_at", sa.Integer(), nullable=False),
        )
        op.create_index("ix_thesis_document_thesis_id", "thesis_document", ["thesis_id"])
    if "thesis_document_version" not in tables:
        op.create_table(
            "thesis_document_version",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("thesis_document.id"), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("filename", sa.String(255), nullable=False),
            sa.Column("original_name", sa.String(255), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("note", sa.String(500), nullable=True),
            sa.Column("uploaded_by", sa.Integer(), sa.ForeignKey("user_mgmt.id"), nullable=True),
            sa.Column("created_at", sa.Integer(), nullable=False),
        )
        op.create_index("ix_thesis_document_version_document_id", "thesis_document_version", ["document_id"])
    if "document_comment" not in tables:
        op.create_table(
            "document_comment",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("version_id", sa.Integer(), sa.ForeignKey("thesis_document_version.id"), nullable=False),
            sa.Column("author_id", sa.Integer(), sa.ForeignKey("user_mgmt.id"), nullable=False),
            sa.Column("section", sa.String(100), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.Integer(), nullable=False),
        )
        op.create_index("ix_document_comment_version_id", "document_comment", ["version_id"])


def downgrade():
    op.drop_table("document_comment")
    op.drop_table("thesis_document_version")
    op.drop_table("thesis_document")
