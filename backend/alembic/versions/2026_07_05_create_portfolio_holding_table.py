"""create portfolio_holding table

Revision ID: 92d3e069a43b
Revises: b1ad558c300c
Create Date: 2026-07-05 14:34:15.753766

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92d3e069a43b'
down_revision: Union[str, Sequence[str], None] = 'b1ad558c300c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_holding",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol_id", sa.Integer, sa.ForeignKey("symbol.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shares", sa.Numeric, nullable=False),
        sa.Column("avg_cost", sa.Numeric, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("portfolio_holding")
