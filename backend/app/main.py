"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import analyze, generate, preview, upload

s = get_settings()

app = FastAPI(
    title=s.app_name,
    version=s.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=s.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(analyze.router)
app.include_router(preview.router)
app.include_router(generate.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": s.app_version}
