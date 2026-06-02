"""
backend/main.py
---------------
FastAPI application entry point.

Run:
    cd ocr_draft
    uvicorn backend.main:app --reload --port 8000
"""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.upload import router as upload_router
from backend.api.export import router as export_router
from backend.api.keywords import router as keywords_router

app = FastAPI(
    title="Orbit Optix API",
    description="Bank statement OCR, analysis and lender detection API",
    version="2.0.0",
)

# CORS — include production Render URL plus local dev servers
_default_origins = ",".join([
    "http://localhost:5173",
    "http://localhost:3000",
    "https://capital-infusion-ocr-cbs3.onrender.com",
])
origins = os.environ.get("CORS_ORIGINS", _default_origins).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers — must be registered BEFORE the static-file catch-all
app.include_router(upload_router,   prefix="/api")
app.include_router(export_router,   prefix="/api")
app.include_router(keywords_router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "service": "Orbit Optix API"}


# Serve the built React frontend (production only — skipped if dist doesn't exist yet)
_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
