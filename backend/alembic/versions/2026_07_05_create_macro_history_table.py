"""create macro_history table

Revision ID: bc5377847070
Revises: 38cf1f8621f7
Create Date: 2026-07-05 14:35:07.198518

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bc5377847070'
down_revision: Union[str, Sequence[str], None] = '38cf1f8621f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "macro_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("series", sa.Text, nullable=False),  # fed_funds, vix, treasury_2y, treasury_10y, etc.
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("value", sa.Numeric, nullable=False),
        sa.UniqueConstraint("series", "date", name="uq_macro_history_series_date"),
    )
    op.create_index("ix_macro_history_series_date", "macro_history", ["series", "date"])


def downgrade() -> None:
    op.drop_index("ix_macro_history_series_date")
    op.drop_table("macro_history")
