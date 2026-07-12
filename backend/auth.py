"""Better Auth session bridge — resolve the current user from the session cookie."""

from __future__ import annotations

from urllib.parse import unquote

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
    # When Better Auth's baseURL is https, useSecureCookies defaults to
    # true and the cookie name gets a "__Secure-" prefix. Check both so
    # the bridge works in local dev (http) and production (https).
    raw = (
        request.cookies.get("__Secure-better-auth.session_token")
        or request.cookies.get("better-auth.session_token")
    )
    if not raw:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Cookie value is URL-encoded and has a ".signature" suffix appended
    # by Better Auth (e.g. "token.hmac_signature"). We discard the HMAC
    # and rely on the DB lookup as the auth check — the token is a
    # high-entropy server-side secret, so a forged value simply won't
    # match any session row. The signature is a defense-in-depth layer
    # we're intentionally skipping to keep the bridge simple.
    token = unquote(raw).split(".")[0]

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
