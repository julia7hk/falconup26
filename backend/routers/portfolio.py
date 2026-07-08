"""Portfolio endpoints — manage holdings, view portfolio with live P&L."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from market import get_price_fetcher

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


# ---------- request bodies ----------


class HoldingCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    shares: float = Field(gt=0)
    avg_cost: float = Field(gt=0)


class HoldingUpdate(BaseModel):
    shares: float | None = Field(default=None, gt=0)
    avg_cost: float | None = Field(default=None, gt=0)


# ---------- helpers ----------


async def _get_holding_or_404(session: AsyncSession, holding_id: int) -> dict:
    result = await session.execute(
        text("""
            SELECT ph.id, s.ticker, s.name, ph.shares, ph.avg_cost, ph.created_at
            FROM portfolio_holding ph
            JOIN symbol s ON s.id = ph.symbol_id
            WHERE ph.id = :id
        """),
        {"id": holding_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Holding not found: {holding_id}")
    return {
        "id": row.id,
        "ticker": row.ticker,
        "name": row.name,
        "shares": float(row.shares),
        "avg_cost": float(row.avg_cost),
        "created_at": row.created_at.isoformat(),
    }


# ---------- endpoints ----------


@router.post("/holdings", status_code=201)
async def add_holding(body: HoldingCreate, session: AsyncSession = Depends(get_session)):
    """Add a holding to the portfolio."""
    ticker = body.ticker.upper()

    # Look up symbol
    result = await session.execute(
        text("SELECT id FROM symbol WHERE ticker = :ticker"),
        {"ticker": ticker},
    )
    symbol_row = result.fetchone()
    if not symbol_row:
        raise HTTPException(status_code=404, detail=f"Symbol not in database: {ticker}")

    # Insert holding
    result = await session.execute(
        text("""
            INSERT INTO portfolio_holding (symbol_id, shares, avg_cost)
            VALUES (:symbol_id, :shares, :avg_cost)
            RETURNING id
        """),
        {"symbol_id": symbol_row.id, "shares": body.shares, "avg_cost": body.avg_cost},
    )
    holding_id = result.scalar()
    await session.commit()

    return await _get_holding_or_404(session, holding_id)


@router.get("")
async def get_portfolio(session: AsyncSession = Depends(get_session)):
    """All holdings with live prices and P&L."""
    result = await session.execute(text("""
        SELECT ph.id, s.ticker, s.name, s.type, s.sector, s.leverage_factor,
               ph.shares, ph.avg_cost
        FROM portfolio_holding ph
        JOIN symbol s ON s.id = ph.symbol_id
        ORDER BY s.ticker
    """))
    rows = result.fetchall()

    if not rows:
        return {"holdings": [], "total_value": 0, "total_cost": 0, "total_pnl": 0}

    # Fetch live quotes for all tickers
    fetcher = get_price_fetcher()
    holdings = []
    total_value = 0.0
    total_cost = 0.0

    for row in rows:
        shares = float(row.shares)
        avg_cost = float(row.avg_cost)
        cost_basis = shares * avg_cost

        # Best-effort live quote
        try:
            quote = fetcher.get_quote(row.ticker)
            price = quote.price
            change = quote.change
            change_percent = quote.change_percent
        except Exception:
            price = None
            change = None
            change_percent = None

        market_value = shares * price if price else None
        pnl = market_value - cost_basis if market_value else None
        pnl_percent = (pnl / cost_basis * 100) if pnl is not None and cost_basis else None

        if market_value is not None:
            total_value += market_value
        total_cost += cost_basis

        holdings.append({
            "id": row.id,
            "ticker": row.ticker,
            "name": row.name,
            "type": row.type,
            "sector": row.sector,
            "leverage_factor": float(row.leverage_factor),
            "shares": shares,
            "avg_cost": avg_cost,
            "cost_basis": cost_basis,
            "price": price,
            "change": change,
            "change_percent": change_percent,
            "market_value": market_value,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
        })

    return {
        "holdings": holdings,
        "total_value": total_value,
        "total_cost": total_cost,
        "total_pnl": total_value - total_cost,
    }


@router.put("/holdings/{holding_id}")
async def update_holding(
    holding_id: int,
    body: HoldingUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update shares and/or avg_cost for a holding."""
    # Verify it exists
    await _get_holding_or_404(session, holding_id)

    if body.shares is None and body.avg_cost is None:
        raise HTTPException(status_code=400, detail="Nothing to update")

    sets = []
    params: dict = {"id": holding_id}
    if body.shares is not None:
        sets.append("shares = :shares")
        params["shares"] = body.shares
    if body.avg_cost is not None:
        sets.append("avg_cost = :avg_cost")
        params["avg_cost"] = body.avg_cost
    sets.append("updated_at = now()")

    await session.execute(
        text(f"UPDATE portfolio_holding SET {', '.join(sets)} WHERE id = :id"),
        params,
    )
    await session.commit()

    return await _get_holding_or_404(session, holding_id)


@router.delete("/holdings/{holding_id}", status_code=204)
async def delete_holding(
    holding_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Remove a holding from the portfolio."""
    await _get_holding_or_404(session, holding_id)
    await session.execute(
        text("DELETE FROM portfolio_holding WHERE id = :id"),
        {"id": holding_id},
    )
    await session.commit()
