"""Admin endpoints — manual data refresh from Azure DevOps."""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import settings

router = APIRouter()

# Project root = three levels up from this file (backend/app/api/admin.py)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class RefreshStatus(BaseModel):
    success: bool
    bugs_ingested: bool
    wiki_ingested: bool
    bugs_error: Optional[str] = None
    wiki_error: Optional[str] = None
    index_age_hours: Optional[float] = None
    message: str


@router.post("/refresh", response_model=RefreshStatus)
async def refresh_index():
    """
    Manually trigger a fresh pull from Azure DevOps and rebuild the vector index.

    - Fetches latest bugs and wiki pages from Azure DevOps
    - Rebuilds the local numpy vector index (data/vector_index/)
    - Also updates the Redis vector index if Redis Stack is available
    - Use this whenever new bugs have been filed or wiki pages updated and you
      do not want to wait for the automatic 48-hour refresh cycle.
    """
    loop = asyncio.get_event_loop()
    ingested: dict[str, bool] = {}
    errors: dict[str, Optional[str]] = {}
    _env = os.environ.copy()
    _env["PYTHONPATH"] = str(PROJECT_ROOT)

    for name, script in [("bugs", "scripts/ingest_bugs.py"), ("wiki", "scripts/ingest_wiki.py")]:
        result = await loop.run_in_executor(
            None,
            lambda s=script: subprocess.run(
                [sys.executable, s],
                capture_output=True,
                text=True,
                cwd=str(PROJECT_ROOT),
                env=_env,
            ),
        )
        ingested[name] = result.returncode == 0
        errors[name] = result.stderr.strip() if result.returncode != 0 else None

    index_dir = Path(settings.vector_index_dir)
    bugs_emb = index_dir / "bugs_embeddings.npy"
    wiki_emb = index_dir / "wiki_embeddings.npy"
    age_hours: Optional[float] = None
    if bugs_emb.exists() and wiki_emb.exists():
        age_hours = round(
            (time.time() - min(bugs_emb.stat().st_mtime, wiki_emb.stat().st_mtime)) / 3600,
            2,
        )

    success = ingested.get("bugs", False) and ingested.get("wiki", False)
    message = (
        "Vector index refreshed successfully from Azure DevOps."
        if success
        else "One or more ingest scripts failed — check errors for details."
    )

    return RefreshStatus(
        success=success,
        bugs_ingested=ingested.get("bugs", False),
        wiki_ingested=ingested.get("wiki", False),
        bugs_error=errors.get("bugs"),
        wiki_error=errors.get("wiki"),
        index_age_hours=age_hours,
        message=message,
    )


@router.get("/index-status")
async def index_status():
    """
    Returns the current age and size of the local vector index files,
    so the frontend can display when the index was last refreshed.
    """
    index_dir = Path(settings.vector_index_dir)
    bugs_emb = index_dir / "bugs_embeddings.npy"
    wiki_emb = index_dir / "wiki_embeddings.npy"

    def file_info(p: Path) -> dict:
        if not p.exists():
            return {"exists": False}
        age_hours = round((time.time() - p.stat().st_mtime) / 3600, 2)
        size_kb = round(p.stat().st_size / 1024, 1)
        return {"exists": True, "age_hours": age_hours, "size_kb": size_kb}

    bugs_info = file_info(bugs_emb)
    wiki_info = file_info(wiki_emb)

    stale = False
    age_hours = None
    if bugs_info.get("exists") and wiki_info.get("exists"):
        age_hours = max(bugs_info["age_hours"], wiki_info["age_hours"])
        stale = age_hours > 48

    return {
        "bugs_index": bugs_info,
        "wiki_index": wiki_info,
        "oldest_age_hours": age_hours,
        "stale": stale,
        "refresh_threshold_hours": 48,
    }
