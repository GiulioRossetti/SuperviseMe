"""add thesis interest and publisher

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-04 16:00:00

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)

    thesis_columns = {c["name"] for c in inspector.get_columns("thesis")}
    with op.batch_alter_table("thesis", schema=None) as batch_op:
        if "publisher_id" not in thesis_columns:
            batch_op.add_column(sa.Column("publisher_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                batch_op.f("fk_thesis_publisher_id_user_mgmt"),
                "user_mgmt",
                ["publisher_id"],
                ["id"],
            )

    tables = set(inspector.get_table_names())
    if "thesis_interest" not in tables:
        op.create_table(
            "thesis_interest",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("thesis_id", sa.Integer(), nullable=False),
            sa.Column("student_id", sa.Integer(), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["student_id"], ["user_mgmt.id"], name=op.f("fk_thesis_interest_student_id_user_mgmt")),
            sa.ForeignKeyConstraint(["thesis_id"], ["thesis.id"], name=op.f("fk_thesis_interest_thesis_id_thesis")),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_thesis_interest")),
        )
        op.create_index(op.f("ix_thesis_interest_thesis_id"), "thesis_interest", ["thesis_id"], unique=False)
        op.create_index(op.f("ix_thesis_interest_student_id"), "thesis_interest", ["student_id"], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)

    tables = set(inspector.get_table_names())
    if "thesis_interest" in tables:
        try:
            op.drop_index(op.f("ix_thesis_interest_student_id"), table_name="thesis_interest")
        except Exception:
            pass
        try:
            op.drop_index(op.f("ix_thesis_interest_thesis_id"), table_name="thesis_interest")
        except Exception:
            pass
        op.drop_table("thesis_interest")

    thesis_columns = {c["name"] for c in inspector.get_columns("thesis")}
    if "publisher_id" in thesis_columns:
        with op.batch_alter_table("thesis", schema=None) as batch_op:
            batch_op.drop_constraint(batch_op.f("fk_thesis_publisher_id_user_mgmt"), type_="foreignkey")
            batch_op.drop_column("publisher_id")
