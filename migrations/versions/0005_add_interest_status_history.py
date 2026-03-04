"""add interest status history

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-04 16:30:00

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = {c["name"] for c in inspector.get_columns("thesis_interest")}

    with op.batch_alter_table("thesis_interest", schema=None) as batch_op:
        if "status" not in columns:
            batch_op.add_column(sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"))
        if "handled_at" not in columns:
            batch_op.add_column(sa.Column("handled_at", sa.Integer(), nullable=True))
        if "handled_by_id" not in columns:
            batch_op.add_column(sa.Column("handled_by_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                batch_op.f("fk_thesis_interest_handled_by_id_user_mgmt"),
                "user_mgmt",
                ["handled_by_id"],
                ["id"],
            )

    op.execute("UPDATE thesis_interest SET status='pending' WHERE status IS NULL OR status='' ")


def downgrade():
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = {c["name"] for c in inspector.get_columns("thesis_interest")}

    with op.batch_alter_table("thesis_interest", schema=None) as batch_op:
        if "handled_by_id" in columns:
            batch_op.drop_constraint(batch_op.f("fk_thesis_interest_handled_by_id_user_mgmt"), type_="foreignkey")
            batch_op.drop_column("handled_by_id")
        if "handled_at" in columns:
            batch_op.drop_column("handled_at")
        if "status" in columns:
            batch_op.drop_column("status")
