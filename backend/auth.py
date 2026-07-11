"""Better Auth session bridge — resolve the current user from the session cookie."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """FastAPI dependency that reads the Better Auth session cookie,
    looks up the token in the shared session table, and returns the user.

    Returns a dict with id, name, email. Raises 401 if no valid session.
    """
    token = request.cookies.get("better-auth.session_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    result = await session.execute(
        text("""
            SELECT u.id, u.name, u.email
            FROM session s
            JOIN "user" u ON u.id = s."userId"
            WHERE s.token = :token
              AND s."expiresAt" > now()
        """),
        {"token": token},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return {"id": row.id, "name": row.name, "email": row.email}
