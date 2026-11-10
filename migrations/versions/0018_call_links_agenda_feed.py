"""call links on meetings/slots and personal agenda feed token

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def _cols(insp, table):
    return {c["name"] for c in insp.get_columns(table)}


def upgrade():
    insp = inspect(op.get_bind())
    if "call_url" not in _cols(insp, "meeting"):
        with op.batch_alter_table("meeting", schema=None) as b:
            b.add_column(sa.Column("call_url", sa.String(500), nullable=True))
    if "call_url" not in _cols(insp, "availability_slot"):
        with op.batch_alter_table("availability_slot", schema=None) as b:
            b.add_column(sa.Column("call_url", sa.String(500), nullable=True))
    if "agenda_token" not in _cols(insp, "user_mgmt"):
        with op.batch_alter_table("user_mgmt", schema=None) as b:
            b.add_column(sa.Column("agenda_token", sa.String(64), nullable=True))
            b.create_unique_constraint("uq_user_mgmt_agenda_token", ["agenda_token"])


def downgrade():
    with op.batch_alter_table("user_mgmt", schema=None) as b:
        b.drop_constraint("uq_user_mgmt_agenda_token", type_="unique")
        b.drop_column("agenda_token")
    with op.batch_alter_table("availability_slot", schema=None) as b:
        b.drop_column("call_url")
    with op.batch_alter_table("meeting", schema=None) as b:
        b.drop_column("call_url")
