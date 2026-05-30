"""add source and external_id to notices

Revision ID: 524e2821b7fa
Revises: daa01a1e7b35
Create Date: 2026-05-30
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "524e2821b7fa"
down_revision: Union[str, Sequence[str], None] = "daa01a1e7b35"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("notices", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("source", sa.String(10), nullable=False, server_default="user")
        )
        batch_op.add_column(
            sa.Column("external_id", sa.String(512), nullable=True)
        )
        batch_op.create_unique_constraint("uq_notices_external_id", ["external_id"])


def downgrade() -> None:
    with op.batch_alter_table("notices", schema=None) as batch_op:
        batch_op.drop_constraint("uq_notices_external_id", type_="unique")
        batch_op.drop_column("external_id")
        batch_op.drop_column("source")
