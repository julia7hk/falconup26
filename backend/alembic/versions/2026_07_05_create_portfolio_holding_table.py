"""create portfolio_holding table

Revision ID: 92d3e069a43b
Revises: b1ad558c300c
Create Date: 2026-07-05 14:34:15.753766

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '92d3e069a43b'
down_revision: Union[str, Sequence[str], None] = 'b1ad558c300c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE portfolio_holding (
            id serial PRIMARY KEY,
            symbol_id integer NOT NULL REFERENCES symbol(id) ON DELETE CASCADE,
            shares numeric NOT NULL,
            avg_cost numeric NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE portfolio_holding")
