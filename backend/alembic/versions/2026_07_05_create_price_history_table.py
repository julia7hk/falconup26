"""create price_history table

Revision ID: 38cf1f8621f7
Revises: 92d3e069a43b
Create Date: 2026-07-05 14:34:55.088544

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '38cf1f8621f7'
down_revision: Union[str, Sequence[str], None] = '92d3e069a43b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE price_history (
            id serial PRIMARY KEY,
            symbol_id integer NOT NULL REFERENCES symbol(id) ON DELETE CASCADE,
            date date NOT NULL,
            open numeric NOT NULL,
            high numeric NOT NULL,
            low numeric NOT NULL,
            close numeric NOT NULL,
            volume bigint NOT NULL,
            CONSTRAINT uq_price_history_symbol_date UNIQUE (symbol_id, date)
        )
    """)
    op.execute("CREATE INDEX ix_price_history_symbol_date ON price_history (symbol_id, date)")


def downgrade() -> None:
    op.execute("DROP TABLE price_history")
