from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.api import import_router, analysis_router

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

app.include_router(import_router)
app.include_router(analysis_router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
