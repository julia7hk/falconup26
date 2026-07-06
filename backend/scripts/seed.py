"""Seed the symbol table with a starter set of common symbols.

Usage:
    uv run python -m scripts.seed
"""

import asyncio

from sqlalchemy import text

from db import async_session

SYMBOLS = [
    # Your holdings
    {"ticker": "QQQ", "name": "Invesco QQQ Trust", "type": "etf", "sector": "Technology", "industry": "Large Cap Growth", "leverage_factor": 1},
    {"ticker": "TQQQ", "name": "ProShares UltraPro QQQ", "type": "etf", "sector": "Technology", "industry": "Leveraged Large Cap Growth", "leverage_factor": 3},
    {"ticker": "SOXL", "name": "Direxion Semiconductor Bull 3X", "type": "etf", "sector": "Semiconductors", "industry": "Leveraged Semiconductors", "leverage_factor": 3},
    {"ticker": "NVDA", "name": "NVIDIA Corporation", "type": "stock", "sector": "Technology", "industry": "Semiconductors"},
    # Popular index ETFs
    {"ticker": "SPY", "name": "SPDR S&P 500 ETF Trust", "type": "etf", "sector": "Broad Market", "industry": "Large Cap Blend"},
    {"ticker": "VOO", "name": "Vanguard S&P 500 ETF", "type": "etf", "sector": "Broad Market", "industry": "Large Cap Blend"},
    {"ticker": "VTI", "name": "Vanguard Total Stock Market ETF", "type": "etf", "sector": "Broad Market", "industry": "Total Market"},
    {"ticker": "DIA", "name": "SPDR Dow Jones Industrial Average ETF", "type": "etf", "sector": "Broad Market", "industry": "Large Cap Value"},
    # Leveraged ETFs
    {"ticker": "SQQQ", "name": "ProShares UltraPro Short QQQ", "type": "etf", "sector": "Technology", "industry": "Inverse Leveraged Large Cap Growth", "leverage_factor": -3},
    {"ticker": "SPXL", "name": "Direxion Daily S&P 500 Bull 3X", "type": "etf", "sector": "Broad Market", "industry": "Leveraged Large Cap Blend", "leverage_factor": 3},
    # Big tech stocks
    {"ticker": "AAPL", "name": "Apple Inc.", "type": "stock", "sector": "Technology", "industry": "Consumer Electronics"},
    {"ticker": "MSFT", "name": "Microsoft Corporation", "type": "stock", "sector": "Technology", "industry": "Software"},
    {"ticker": "GOOGL", "name": "Alphabet Inc.", "type": "stock", "sector": "Technology", "industry": "Internet Services"},
    {"ticker": "AMZN", "name": "Amazon.com Inc.", "type": "stock", "sector": "Technology", "industry": "E-Commerce"},
    {"ticker": "META", "name": "Meta Platforms Inc.", "type": "stock", "sector": "Technology", "industry": "Social Media"},
    {"ticker": "TSLA", "name": "Tesla Inc.", "type": "stock", "sector": "Consumer Cyclical", "industry": "Auto Manufacturers"},
]


async def main():
    async with async_session() as session:
        for sym in SYMBOLS:
            await session.execute(
                text("""
                    INSERT INTO symbol (ticker, name, type, sector, industry, leverage_factor)
                    VALUES (:ticker, :name, :type, :sector, :industry, :leverage_factor)
                    ON CONFLICT (ticker) DO NOTHING
                """),
                {
                    "ticker": sym["ticker"],
                    "name": sym["name"],
                    "type": sym["type"],
                    "sector": sym.get("sector"),
                    "industry": sym.get("industry"),
                    "leverage_factor": sym.get("leverage_factor", 1),
                },
            )
        await session.commit()
    print(f"Seeded {len(SYMBOLS)} symbols")


if __name__ == "__main__":
    asyncio.run(main())
