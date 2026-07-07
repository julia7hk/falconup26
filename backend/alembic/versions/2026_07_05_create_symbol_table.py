"""create symbol table

Revision ID: b1ad558c300c
Revises:
Create Date: 2026-07-05 14:22:19.031357

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b1ad558c300c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE symbol (
            id serial PRIMARY KEY,
            ticker text NOT NULL UNIQUE,
            name text,
            type text NOT NULL,
            sector text,
            industry text,
            leverage_factor numeric NOT NULL DEFAULT 1,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE symbol")
