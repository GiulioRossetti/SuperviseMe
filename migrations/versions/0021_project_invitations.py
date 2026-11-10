"""project collaboration invitations (status column)

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

TABLE = "research_project_collaborator"


def upgrade():
    cols = {c["name"] for c in inspect(op.get_bind()).get_columns(TABLE)}
    if "status" in cols:
        return
    with op.batch_alter_table(TABLE) as batch:
        batch.add_column(sa.Column("status", sa.String(20), nullable=False, server_default="accepted"))


def downgrade():
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_column("status")
