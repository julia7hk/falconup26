"""create price_history table

Revision ID: 38cf1f8621f7
Revises: 92d3e069a43b
Create Date: 2026-07-05 14:34:55.088544

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '38cf1f8621f7'
down_revision: Union[str, Sequence[str], None] = '92d3e069a43b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "price_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol_id", sa.Integer, sa.ForeignKey("symbol.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("open", sa.Numeric, nullable=False),
        sa.Column("high", sa.Numeric, nullable=False),
        sa.Column("low", sa.Numeric, nullable=False),
        sa.Column("close", sa.Numeric, nullable=False),
        sa.Column("volume", sa.BigInteger, nullable=False),
        sa.UniqueConstraint("symbol_id", "date", name="uq_price_history_symbol_date"),
    )
    op.create_index("ix_price_history_symbol_date", "price_history", ["symbol_id", "date"])


def downgrade() -> None:
    op.drop_index("ix_price_history_symbol_date")
    op.drop_table("price_history")
