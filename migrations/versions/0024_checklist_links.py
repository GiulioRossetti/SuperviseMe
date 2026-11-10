"""links on graduation checklist templates and steps

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

COLUMNS = {
    "checklist_template": [("info_url", sa.String(500)), ("resources", sa.Text())],
    "checklist_template_item": [("url", sa.String(500))],
    "thesis_checklist_item": [("url", sa.String(500))],
}


def upgrade():
    insp = inspect(op.get_bind())
    for table, cols in COLUMNS.items():
        have = {c["name"] for c in insp.get_columns(table)}
        todo = [(n, t) for n, t in cols if n not in have]
        if todo:
            with op.batch_alter_table(table) as batch:
                for name, type_ in todo:
                    batch.add_column(sa.Column(name, type_, nullable=True))


def downgrade():
    for table, cols in COLUMNS.items():
        with op.batch_alter_table(table) as batch:
            for name, _type in cols:
                batch.drop_column(name)
