"""
Script to ingest historical bugs from Azure DevOps
and sync them into the local vector store and Azure AI Search index.
"""

import asyncio
import re
from typing import Any, Dict, List

from backend.app.config import settings
from backend.app.services.azure_devops_connector import AzureDevOpsConnector
from backend.app.services.local_vector_search_service import LocalVectorSearchService


def _safe_azure_search_id(raw_value: Any, prefix: str = "bug") -> str:
    """Convert identifiers into Azure AI Search-safe keys."""
    candidate = str(raw_value or "").strip()
    if not candidate:
        candidate = f"{prefix}_untitled"

    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", candidate)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = f"{prefix}_untitled"

    return f"{prefix}_{cleaned}" if not cleaned.startswith(f"{prefix}_") else cleaned


def _normalize_bug_for_azure_search(bug: Dict[str, Any]) -> Dict[str, Any]:
    """Map Azure DevOps bug objects into the Azure AI Search document schema."""
    title = bug.get("title") or ""
    description = bug.get("description") or bug.get("content") or ""
    content = bug.get("description") or bug.get("content") or description
    url = bug.get("url") or bug.get("web_url") or ""
    category = bug.get("category") or "bug"
    original_id = bug.get("id")
    root_cause_analysis = bug.get("root_cause_analysis") or ""
    return {
        "id": _safe_azure_search_id(original_id if original_id is not None else title or url or len(str(bug)), prefix="bug"),
        "title": title,
        "description": description,
        "content": content,
        "root_cause_analysis": root_cause_analysis,
        "path": bug.get("path") or "",
        "url": url,
        "category": category,
        "source": "azure_devops",
    }


async def _ingest_to_azure_ai_search(bugs: List[Dict[str, Any]]) -> int:
    """Upload bugs to Azure AI Search when the service is configured."""
    if not settings.azure_search_enabled:
        print("⚠️  Azure AI Search is not configured; skipping Azure Search ingestion.")
        return 0

    try:
        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents import SearchClient

        client = SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index_name,
            credential=AzureKeyCredential(settings.azure_search_api_key),
        )

        documents = [_normalize_bug_for_azure_search(bug) for bug in bugs]
        if not documents:
            print("📦 No Azure AI Search documents to upload.")
            return 0

        result = client.merge_or_upload_documents(documents=documents)
        uploaded = sum(1 for item in result if getattr(item, "succeeded", False))
        print(f"📦 Upserted {uploaded} bug document(s) in Azure AI Search index '{settings.azure_search_index_name}'")
        return uploaded
    except Exception as exc:  # pragma: no cover - runtime env dependency
        print(f"❌ Azure AI Search ingestion failed: {exc}")
        return 0


async def _fetch_full_bug_backlog(connector: AzureDevOpsConnector, top_k: int = 200) -> List[Dict[str, Any]]:
    """Fetch a broader backlog of issue work items instead of only a few hard-coded keywords."""
    try:
        from azure.devops.v7_1.work_item_tracking.models import Wiql

        wiql = Wiql(query=f"""
            SELECT [System.Id]
            FROM WorkItems
            WHERE [System.TeamProject] = '{connector.project}'
            AND [System.WorkItemType] = 'Issue'
            ORDER BY [System.ChangedDate] DESC
        """)

        results = connector.work_item_client.query_by_wiql(wiql, top=top_k)
        issue_ids = [wi.id for wi in (results.work_items or [])]
        bugs: List[Dict[str, Any]] = []
        seen_ids = set()

        for work_item_id in issue_ids:
            if work_item_id in seen_ids:
                continue
            seen_ids.add(work_item_id)

            try:
                item = connector.work_item_client.get_work_item(work_item_id, expand=1)
            except Exception as exc:  # pragma: no cover - backend service may return stale IDs
                print(f"[BugIngest] Skipping inaccessible work item {work_item_id}: {exc}")
                continue

            fields = item.fields or {}
            bugs.append(
                {
                    "id": str(item.id),
                    "title": fields.get("System.Title", ""),
                    "description": fields.get("System.Description", ""),
                    "root_cause_analysis": connector._extract_root_cause_analysis(fields),
                    "state": fields.get("System.State", ""),
                    "assigned_to": connector._extract_assigned_to(fields),
                    "url": item.url,
                }
            )

        return bugs
    except Exception as exc:  # pragma: no cover - runtime env dependency
        print(f"[BugIngest] Full backlog fetch failed: {exc}")
        return []


async def ingest_bugs():
    """
    Fetch a broader backlog of bugs from Azure DevOps and embed them into the local vector index,
    and optionally sync them into Azure AI Search.
    """
    print("🔍 Starting bug ingestion from Azure DevOps...")

    try:
        connector = AzureDevOpsConnector()
        local_service = LocalVectorSearchService()

        if local_service.enabled:
            print("✅ Local vector search enabled — embeddings will be persisted locally.")
        else:
            print(f"⚠️  Local vector search disabled: {local_service.init_error}")

        if settings.azure_search_enabled:
            print(f"✅ Azure AI Search enabled — index '{settings.azure_search_index_name}' will receive bug documents.")
        else:
            print("⚠️  Azure AI Search not configured — only local indexing will run.")

        # Keep the old variable name so the rest of the script is unchanged.
        vector_service = local_service

        print("  🔎 Fetching the broader Azure DevOps Issue backlog (not limited to a few hard-coded terms)...")
        all_bugs = await _fetch_full_bug_backlog(connector, top_k=250)
        print(f"     ✓ Found {len(all_bugs)} bugs in the backlog")

        print(f"\n✅ Total bugs ingested: {len(all_bugs)}")

        indexed_count = vector_service.index_bugs(all_bugs)
        print(f"📦 Indexed {indexed_count} new bug(s) in local vector store")

        azure_indexed_count = await _ingest_to_azure_ai_search(all_bugs)
        print(f"📦 Azure AI Search upload summary: {azure_indexed_count} document(s)")

        if all_bugs:
            print("\n📌 Sample bug:")
            bug = all_bugs[0]
            print(f"   ID: {bug['id']}")
            print(f"   Title: {bug['title']}")
            print(f"   State: {bug['state']}")

    except Exception as e:
        print(f"❌ Error during bug ingestion: {str(e)}")
        print("Make sure your Azure DevOps credentials are set in .env")


if __name__ == "__main__":
    asyncio.run(ingest_bugs())