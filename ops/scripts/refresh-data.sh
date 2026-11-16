#!/usr/bin/env bash
# Nightly incremental refresh of price_history + macro_history.
#
# Run by the falconup-backfill systemd timer on oc40. Safe to run by hand.
# Idempotent: scripts/backfill.py does an incremental catch-up from the last
# stored date and upserts (ON CONFLICT DO UPDATE), so re-running is harmless
# and picks up vendor restatements of already-stored bars.
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/_proj/falconup26}"
cd "$REPO_DIR"

# Neither direnv nor .env load in a non-interactive shell, and uv is not on
# the default PATH. See CLAUDE.md "direnv not loaded in non-interactive shells".
export PATH="$HOME/.local/bin:$PATH"
set -a
# shellcheck disable=SC1091
. ./.env
set +a

# .env builds DATABASE_URL against PGHOST=172.17.0.1 (the Docker bridge, for
# containers). Bare-metal runs talk to Postgres over localhost instead.
export DATABASE_URL="postgresql://${PGUSER}:${PGPASSWORD}@localhost:${PGPORT}/${PGDATABASE}"

cd backend
exec uv run python -m scripts.backfill "$@"
