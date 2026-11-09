"""add thesis_image and thesis_link tables

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    tables = set(inspect(op.get_bind()).get_table_names())

    if "thesis_image" not in tables:
        op.create_table(
            "thesis_image",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("thesis_id", sa.Integer(), nullable=False),
            sa.Column("filename", sa.String(length=120), nullable=False),
            sa.Column("caption", sa.String(length=200), nullable=True),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["thesis_id"], ["thesis.id"], name=op.f("fk_thesis_image_thesis_id_thesis")),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_thesis_image")),
            sa.UniqueConstraint("filename", name=op.f("uq_thesis_image_filename")),
        )
        op.create_index(op.f("ix_thesis_image_thesis_id"), "thesis_image", ["thesis_id"], unique=False)

    if "thesis_link" not in tables:
        op.create_table(
            "thesis_link",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("thesis_id", sa.Integer(), nullable=False),
            sa.Column("url", sa.String(length=500), nullable=False),
            sa.Column("label", sa.String(length=200), nullable=True),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["thesis_id"], ["thesis.id"], name=op.f("fk_thesis_link_thesis_id_thesis")),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_thesis_link")),
        )
        op.create_index(op.f("ix_thesis_link_thesis_id"), "thesis_link", ["thesis_id"], unique=False)


def downgrade():
    op.drop_table("thesis_link")
    op.drop_table("thesis_image")
