"""better_auth_tables + add user_id to portfolio_holding

Revision ID: a1b2c3d4e5f6
Revises: f4a7c1e83d20
Create Date: 2026-07-11 00:00:00.000000

Better Auth tables use camelCase columns to match Better Auth's Prisma
adapter, which maps model fields to column names without snake_case
translation. This is isolated to the auth subsystem; rest of the schema
stays snake_case.

Also truncates portfolio_holding (test data only) and adds user_id FK
so holdings are per-user. Replaces the UNIQUE on symbol_id with a
UNIQUE on (user_id, symbol_id).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f4a7c1e83d20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- Better Auth tables --

    op.execute("""
        CREATE TABLE "user" (
            id              text PRIMARY KEY,
            name            text NOT NULL,
            email           text NOT NULL UNIQUE,
            "emailVerified" boolean NOT NULL DEFAULT false,
            image           text,
            "createdAt"     timestamptz NOT NULL DEFAULT now(),
            "updatedAt"     timestamptz NOT NULL,
            role            text,
            banned          boolean DEFAULT false,
            "banReason"     text,
            "banExpires"    timestamptz
        )
    """)

    op.execute("""
        CREATE TABLE session (
            id               text PRIMARY KEY,
            "expiresAt"      timestamptz NOT NULL,
            token            text NOT NULL UNIQUE,
            "createdAt"      timestamptz NOT NULL DEFAULT now(),
            "updatedAt"      timestamptz NOT NULL,
            "ipAddress"      text,
            "userAgent"      text,
            "userId"         text NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            "impersonatedBy" text
        )
    """)
    op.execute('CREATE INDEX "ix_session_userId" ON session ("userId")')

    op.execute("""
        CREATE TABLE account (
            id                      text PRIMARY KEY,
            "accountId"             text NOT NULL,
            "providerId"            text NOT NULL,
            "userId"                text NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            "accessToken"           text,
            "refreshToken"          text,
            "idToken"               text,
            "accessTokenExpiresAt"  timestamptz,
            "refreshTokenExpiresAt" timestamptz,
            scope                   text,
            password                text,
            "createdAt"             timestamptz NOT NULL DEFAULT now(),
            "updatedAt"             timestamptz NOT NULL
        )
    """)
    op.execute('CREATE INDEX "ix_account_userId" ON account ("userId")')

    op.execute("""
        CREATE TABLE verification (
            id          text PRIMARY KEY,
            identifier  text NOT NULL,
            value       text NOT NULL,
            "expiresAt" timestamptz NOT NULL,
            "createdAt" timestamptz NOT NULL DEFAULT now(),
            "updatedAt" timestamptz NOT NULL
        )
    """)
    op.execute(
        "CREATE INDEX ix_verification_identifier ON verification (identifier)"
    )

    # -- Add user_id to portfolio_holding --

    op.execute("TRUNCATE portfolio_holding")
    op.execute("""
        ALTER TABLE portfolio_holding
        DROP CONSTRAINT portfolio_holding_symbol_id_key
    """)
    op.execute("""
        ALTER TABLE portfolio_holding
        ADD COLUMN user_id text NOT NULL REFERENCES "user"(id) ON DELETE CASCADE
    """)
    op.execute("""
        ALTER TABLE portfolio_holding
        ADD CONSTRAINT portfolio_holding_user_id_symbol_id_key
        UNIQUE (user_id, symbol_id)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE portfolio_holding
        DROP CONSTRAINT portfolio_holding_user_id_symbol_id_key
    """)
    op.execute("ALTER TABLE portfolio_holding DROP COLUMN user_id")
    op.execute("""
        ALTER TABLE portfolio_holding
        ADD CONSTRAINT portfolio_holding_symbol_id_key UNIQUE (symbol_id)
    """)
    op.execute("DROP TABLE verification")
    op.execute("DROP TABLE account")
    op.execute("DROP TABLE session")
    op.execute('DROP TABLE "user"')
