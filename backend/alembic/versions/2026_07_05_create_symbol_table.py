"""create symbol table

Revision ID: b1ad558c300c
Revises: 
Create Date: 2026-07-05 14:22:19.031357

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1ad558c300c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "symbol",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ticker", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text),
        sa.Column("type", sa.Text, nullable=False),  # 'etf' or 'stock'
        sa.Column("sector", sa.Text),
        sa.Column("industry", sa.Text),
        sa.Column("leverage_factor", sa.Numeric, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("symbol")
