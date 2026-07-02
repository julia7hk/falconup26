from fastapi import FastAPI

from routers.symbols import router as symbols_router

app = FastAPI(title="FalconUp", version="0.1.0")

app.include_router(symbols_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
