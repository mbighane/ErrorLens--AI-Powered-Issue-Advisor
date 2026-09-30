from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .api.issues import router as issues_router
from .api.admin import router as admin_router
from .logging_config import configure_local_logging, request_id_context, shutdown_local_logging
import asyncio
import logging
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

import numpy as np

INDEX_REFRESH_SECONDS = settings.index_refresh_hours * 3600

# Project root = two levels up from this file (backend/app/main.py)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

app = FastAPI(
    title="ErrorLens API",
    description="AI-Powered Issue Advisor",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit default
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(issues_router, prefix="/api/issues", tags=["issues"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])

@app.on_event("startup")
async def auto_ingest_if_empty():
    if settings.is_on_prem_deployment:
        configure_local_logging("backend")

    if not settings.is_on_prem_deployment:
        print("✅ Azure deployment uses the managed Azure AI Search index; skipping local vector index checks.")
        return

    index_dir = Path(settings.vector_index_dir)
    bugs_emb = index_dir / "bugs_embeddings.npy"
    wiki_emb = index_dir / "wiki_embeddings.npy"

    if settings.is_on_prem_deployment:
        for embedding_path, metadata_name in (
            (bugs_emb, "bugs_metadata.json"),
            (wiki_emb, "wiki_metadata.json"),
        ):
            if embedding_path.exists():
                try:
                    dimensions = np.load(embedding_path, mmap_mode="r").shape[1]
                except (OSError, IndexError, ValueError):
                    dimensions = None
                if dimensions != settings.ollama_embedding_dims:
                    print(
                        f"⚠️  Removing incompatible local index {embedding_path} "
                        f"({dimensions} dimensions; expected {settings.ollama_embedding_dims})."
                    )
                    embedding_path.unlink(missing_ok=True)
                    (index_dir / metadata_name).unlink(missing_ok=True)

    missing = not bugs_emb.exists() or not wiki_emb.exists()
    empty = (bugs_emb.exists() and bugs_emb.stat().st_size == 0) or \
            (wiki_emb.exists() and wiki_emb.stat().st_size == 0)

    # Check age of the oldest index file
    stale = False
    if not missing and not empty:
        oldest_mtime = min(
            bugs_emb.stat().st_mtime,
            wiki_emb.stat().st_mtime,
        )
        age_seconds = time.time() - oldest_mtime
        if age_seconds > INDEX_REFRESH_SECONDS:
            age_hours = age_seconds / 3600
            print(f"⚠️  Vector index is stale ({age_hours:.1f}h old, threshold 48h). Re-ingesting...")
            stale = True

    if missing or empty:
        print("⚠️  Vector index is empty or missing. Running ingest scripts automatically...")
    
    if missing or empty or stale:
        loop = asyncio.get_event_loop()
        _env = os.environ.copy()
        _env["PYTHONPATH"] = str(PROJECT_ROOT)
        _env["PYTHONIOENCODING"] = "utf-8"
        for script in ["scripts/ingest_bugs.py", "scripts/ingest_wiki.py"]:
            print(f"▶️  Running {script}...")
            result = await loop.run_in_executor(
                None,
                lambda s=script: subprocess.run(
                    [sys.executable, s],
                    capture_output=True, text=True, encoding="utf-8",
                    cwd=str(PROJECT_ROOT),
                    env=_env,
                )
            )
            if result.returncode == 0:
                print(f"✅ {script} completed successfully.")
            else:
                print(f"❌ {script} failed:\n{result.stderr}")
    else:
        age_hours = (time.time() - min(bugs_emb.stat().st_mtime, wiki_emb.stat().st_mtime)) / 3600
        print(f"✅ Vector index is fresh ({age_hours:.1f}h old). Skipping ingest.")


@app.on_event("shutdown")
async def close_local_logging():
    if settings.is_on_prem_deployment:
        shutdown_local_logging("backend")


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    supplied_id = request.headers.get("X-Request-ID", "")
    request_id = supplied_id if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", supplied_id) else str(uuid.uuid4())
    token = request_id_context.set(request_id)
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        if settings.is_on_prem_deployment:
            logging.getLogger("errorlens.http").info(
                "HTTP request completed",
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "http_status_code": response.status_code,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                },
            )
        return response
    except Exception:
        if settings.is_on_prem_deployment:
            logging.getLogger("errorlens.http").exception(
                "HTTP request failed",
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                },
            )
        raise
    finally:
        request_id_context.reset(token)

@app.get("/")
async def root():
    return {"message": "ErrorLens API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}