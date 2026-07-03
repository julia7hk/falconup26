from fastapi import FastAPI

from routers.macro import router as macro_router
from routers.symbols import router as symbols_router

app = FastAPI(title="FalconUp", version="0.1.0")

app.include_router(symbols_router)
app.include_router(macro_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
