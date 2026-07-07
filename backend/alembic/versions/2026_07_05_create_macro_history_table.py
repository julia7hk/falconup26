"""create macro_history table

Revision ID: bc5377847070
Revises: 38cf1f8621f7
Create Date: 2026-07-05 14:35:07.198518

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'bc5377847070'
down_revision: Union[str, Sequence[str], None] = '38cf1f8621f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE macro_history (
            id serial PRIMARY KEY,
            series text NOT NULL,
            date date NOT NULL,
            value numeric NOT NULL,
            CONSTRAINT uq_macro_history_series_date UNIQUE (series, date)
        )
    """)
    op.execute("CREATE INDEX ix_macro_history_series_date ON macro_history (series, date)")


def downgrade() -> None:
    op.execute("DROP TABLE macro_history")
