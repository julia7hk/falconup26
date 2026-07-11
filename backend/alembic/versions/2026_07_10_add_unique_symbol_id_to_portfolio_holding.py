"""add unique constraint on portfolio_holding.symbol_id

Revision ID: f4a7c1e83d20
Revises: 92d3e069a43b
Create Date: 2026-07-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f4a7c1e83d20'
down_revision: Union[str, Sequence[str], None] = 'bc5377847070'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE portfolio_holding
        ADD CONSTRAINT portfolio_holding_symbol_id_key UNIQUE (symbol_id)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE portfolio_holding
        DROP CONSTRAINT portfolio_holding_symbol_id_key
    """)
