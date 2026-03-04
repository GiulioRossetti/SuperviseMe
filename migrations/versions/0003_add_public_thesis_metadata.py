"""add public thesis metadata

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-04 12:00:00

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = {c["name"] for c in inspector.get_columns("thesis")}

    with op.batch_alter_table("thesis", schema=None) as batch_op:
        if "short_description" not in columns:
            batch_op.add_column(sa.Column("short_description", sa.Text(), nullable=True))
        if "long_description" not in columns:
            batch_op.add_column(sa.Column("long_description", sa.Text(), nullable=True))
        if "topic" not in columns:
            batch_op.add_column(sa.Column("topic", sa.String(length=120), nullable=True))
        if "prerequisites" not in columns:
            batch_op.add_column(sa.Column("prerequisites", sa.Text(), nullable=True))
        if "is_public" not in columns:
            batch_op.add_column(sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("0")))

    # Backfill defaults/normalized values for existing rows.
    op.execute("UPDATE thesis SET is_public = 0 WHERE is_public IS NULL")
    op.execute("UPDATE thesis SET short_description = substr(description, 1, 220) WHERE short_description IS NULL")
    op.execute("UPDATE thesis SET long_description = description WHERE long_description IS NULL")



def downgrade():
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = {c["name"] for c in inspector.get_columns("thesis")}

    with op.batch_alter_table("thesis", schema=None) as batch_op:
        if "is_public" in columns:
            batch_op.drop_column("is_public")
        if "prerequisites" in columns:
            batch_op.drop_column("prerequisites")
        if "topic" in columns:
            batch_op.drop_column("topic")
        if "long_description" in columns:
            batch_op.drop_column("long_description")
        if "short_description" in columns:
            batch_op.drop_column("short_description")
