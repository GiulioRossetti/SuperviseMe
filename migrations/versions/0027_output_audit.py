"""audit trail of research output changes

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade():
    if "research_output_audit" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "research_output_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("user_mgmt.id")),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("output_id", sa.Integer()),
        sa.Column("title", sa.String(300)),
        sa.Column("project_id", sa.Integer()),
        sa.Column("details", sa.Text()),
        sa.Column("created_at", sa.Integer(), nullable=False))
    op.create_index("ix_research_output_audit_actor_id", "research_output_audit", ["actor_id"])
    op.create_index("ix_research_output_audit_project_id", "research_output_audit", ["project_id"])
    op.create_index("ix_research_output_audit_created_at", "research_output_audit", ["created_at"])


def downgrade():
    op.drop_table("research_output_audit")
