"""
backend/main.py
---------------
FastAPI application entry point.

Run:
    cd ocr_draft
    uvicorn backend.main:app --reload --port 8000
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.upload import router as upload_router
from backend.api.export import router as export_router
from backend.api.keywords import router as keywords_router

app = FastAPI(
    title="Orbit Optix API",
    description="Bank statement OCR, analysis and lender detection API",
    version="2.0.0",
)

# Allow requests from the Vite dev server and any production origin
origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router,   prefix="/api")
app.include_router(export_router,   prefix="/api")
app.include_router(keywords_router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "service": "Orbit Optix API"}
