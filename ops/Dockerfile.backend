FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Run Alembic migrations then start the server
CMD uv run alembic upgrade head && \
    uv run uvicorn main:app --host 0.0.0.0 --port 40401
