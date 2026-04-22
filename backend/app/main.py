from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .api.issues import router as issues_router
from .api.admin import router as admin_router
import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

INDEX_REFRESH_SECONDS = 48 * 3600  # 48 hours

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
    index_dir = Path(settings.vector_index_dir)
    bugs_emb = index_dir / "bugs_embeddings.npy"
    wiki_emb = index_dir / "wiki_embeddings.npy"

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

@app.get("/")
async def root():
    return {"message": "ErrorLens API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}