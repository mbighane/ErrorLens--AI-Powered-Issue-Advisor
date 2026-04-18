from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .api.issues import router as issues_router
import asyncio
import subprocess
import sys
from pathlib import Path

app = FastAPI(
    title="ErrorLens API",
    description="AI-Powered Azure DevOps Issue Solver",
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

@app.on_event("startup")
async def auto_ingest_if_empty():
    index_dir = Path(settings.vector_index_dir)
    bugs_emb = index_dir / "bugs_embeddings.npy"
    wiki_emb = index_dir / "wiki_embeddings.npy"

    missing = not bugs_emb.exists() or not wiki_emb.exists()
    empty = (bugs_emb.exists() and bugs_emb.stat().st_size == 0) or \
            (wiki_emb.exists() and wiki_emb.stat().st_size == 0)

    if missing or empty:
        print("⚠️  Vector index is empty or missing. Running ingest scripts automatically...")
        loop = asyncio.get_event_loop()
        for script in ["scripts/ingest_bugs.py", "scripts/ingest_wiki.py"]:
            print(f"▶️  Running {script}...")
            result = await loop.run_in_executor(
                None,
                lambda s=script: subprocess.run(
                    [sys.executable, s],
                    capture_output=True, text=True
                )
            )
            if result.returncode == 0:
                print(f"✅ {script} completed successfully.")
            else:
                print(f"❌ {script} failed:\n{result.stderr}")
    else:
        print("✅ Vector index already populated. Skipping ingest.")

@app.get("/")
async def root():
    return {"message": "ErrorLens API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}