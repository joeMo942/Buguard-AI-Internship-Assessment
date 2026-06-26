from fastapi import FastAPI
from contextlib import asynccontextmanager
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import import_router, analysis_router, asset_router
from app.dependencies import limiter

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Here we would normally ensure the database connection works
    # Alembic handles the schema creation
    yield
    # Cleanup

app = FastAPI(
    title="DarkAtlas Asset Management API - Track B",
    description="Minimal API with LangChain-powered analysis layer",
    version="0.1.0",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(import_router)
app.include_router(analysis_router)
app.include_router(asset_router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
