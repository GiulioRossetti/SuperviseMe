"""make Thesis.publisher_id NOT NULL (after cleaning orphaned rows)

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-09

Strategy
--------
Thesis rows that have no publisher_id represent proposals that were created
without a known author (unusual but allowed by the original schema).  Rather
than silently deleting data, we:

  1. Find the first admin user and assign publisher_id = admin.id for any
     thesis that has publisher_id IS NULL.  If no admin user exists (unlikely
     but possible in a fresh database) we skip the NOT NULL enforcement.
  2. Set author_id defaults similarly — a thesis without an author is an open
     proposal, so we leave author_id nullable but add an application-level
     note in the model.

NOTE: author_id remains nullable because "proposal without assigned student"
is a valid business state.  Only publisher_id (the person who created/owns
the proposal) is made NOT NULL.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # 1. Find the first admin user
    result = conn.execute(
        text("SELECT id FROM user_mgmt WHERE user_type = 'admin' ORDER BY id LIMIT 1")
    )
    row = result.fetchone()

    if row is None:
        # No admin user; cannot enforce NOT NULL safely.
        print(
            "WARNING migration 0008: no admin user found — "
            "skipping NOT NULL enforcement on thesis.publisher_id. "
            "Re-run after bootstrapping an admin account."
        )
        return

    admin_id = row[0]

    # 2. Patch orphaned rows
    conn.execute(
        text(
            "UPDATE thesis SET publisher_id = :admin_id WHERE publisher_id IS NULL"
        ),
        {"admin_id": admin_id},
    )

    # 3. Now enforce NOT NULL
    with op.batch_alter_table("thesis", schema=None) as batch_op:
        batch_op.alter_column(
            "publisher_id",
            existing_type=sa.Integer(),
            existing_nullable=True,
            nullable=False,
        )


def downgrade():
    with op.batch_alter_table("thesis", schema=None) as batch_op:
        batch_op.alter_column(
            "publisher_id",
            existing_type=sa.Integer(),
            existing_nullable=False,
            nullable=True,
        )
