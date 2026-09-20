"""
Script to ingest wiki pages from Azure DevOps knowledge base
and optionally sync them into Azure AI Search.
"""

import asyncio
import re
from typing import Any, Dict, List

from backend.app.config import settings
from backend.app.services.azure_devops_connector import AzureDevOpsConnector
from backend.app.services.local_vector_search_service import LocalVectorSearchService


def _safe_azure_search_id(raw_value: Any, prefix: str = "wiki") -> str:
    """Convert identifiers into Azure AI Search-safe keys."""
    candidate = str(raw_value or "").strip()
    if not candidate:
        candidate = f"{prefix}_untitled"

    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", candidate)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = f"{prefix}_untitled"

    return f"{prefix}_{cleaned}" if not cleaned.startswith(f"{prefix}_") else cleaned


def _normalize_wiki_for_azure_search(page: Dict[str, Any]) -> Dict[str, Any]:
    """Map Azure DevOps wiki page objects into the Azure AI Search document schema."""
    title = page.get("title") or ""
    content = page.get("content") or page.get("text") or ""
    url = page.get("url") or page.get("web_url") or ""
    original_id = page.get("id")
    return {
        "id": _safe_azure_search_id(original_id if original_id is not None else title or url or len(str(page)), prefix="wiki"),
        "title": title,
        "description": content[:2000] if content else "",
        "content": content,
        "path": page.get("path") or "",
        "url": url,
        "category": "wiki",
        "source": "azure_devops_wiki",
    }


async def _ingest_to_azure_ai_search(pages: List[Dict[str, Any]]) -> int:
    """Upload wiki pages to Azure AI Search when the service is configured."""
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

        documents = [_normalize_wiki_for_azure_search(page) for page in pages]
        if not documents:
            print("📦 No Azure AI Search wiki documents to upload.")
            return 0

        result = client.merge_or_upload_documents(documents=documents)
        uploaded = sum(1 for item in result if getattr(item, "succeeded", False))
        print(f"📦 Upserted {uploaded} wiki document(s) in Azure AI Search index '{settings.azure_search_index_name}'")
        return uploaded
    except Exception as exc:  # pragma: no cover - runtime env dependency
        print(f"❌ Azure AI Search wiki ingestion failed: {exc}")
        return 0


async def _fetch_full_wiki_backlog(connector: AzureDevOpsConnector, top_k: int = 200) -> List[Dict[str, Any]]:
    """Fetch a broader wiki backlog instead of only a few hard-coded terms."""
    import base64
    import json
    import urllib.parse

    import requests

    headers = {
        "Authorization": "Basic " + base64.b64encode(f":{connector.token}".encode("ascii")).decode("ascii"),
        "Accept": "application/json",
    }

    wiki_items: List[Dict[str, Any]] = []
    seen_paths: set[str] = set()

    try:
        wikis_url = f"https://dev.azure.com/{connector.organization}/{connector.project}/_apis/wiki/wikis?api-version=7.1"
        wikis_response = requests.get(wikis_url, headers=headers, timeout=20)
        wikis_response.raise_for_status()
        wikis = wikis_response.json().get("value", [])

        for wiki in wikis:
            wiki_id = wiki.get("id") or wiki.get("name", "")
            if not wiki_id:
                continue

            pages_url = (
                f"https://dev.azure.com/{connector.organization}/{connector.project}"
                f"/_apis/wiki/wikis/{wiki_id}/pages?recursionLevel=2&api-version=7.1"
            )
            pages_response = requests.get(pages_url, headers=headers, timeout=20)
            pages_response.raise_for_status()
            root_page = pages_response.json()

            def _collect_pages(node: Dict[str, Any]) -> List[Dict[str, Any]]:
                pages = [node]
                for sub_page in node.get("subPages", []):
                    pages.extend(_collect_pages(sub_page))
                return pages

            for page in _collect_pages(root_page):
                path = page.get("path", "/")
                if path in seen_paths:
                    continue
                seen_paths.add(path)

                title = path.strip("/").replace("/", " > ") or wiki.get("name", path)
                url = page.get("remoteUrl", "")

                content = ""
                try:
                    encoded_path = urllib.parse.quote(path, safe="")
                    content_url = (
                        f"https://dev.azure.com/{connector.organization}/{connector.project}"
                        f"/_apis/wiki/wikis/{wiki_id}/pages"
                        f"?path={encoded_path}&includeContent=true&api-version=7.1"
                    )
                    content_response = requests.get(content_url, headers=headers, timeout=20)
                    content_response.raise_for_status()
                    raw_bytes = content_response.content
                    try:
                        text = raw_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        text = raw_bytes.decode("latin-1")
                    page_data = json.loads(text)
                    raw_content = page_data.get("content", "")
                    content = raw_content.encode("utf-8", errors="replace").decode("utf-8")
                except Exception:
                    content = ""

                wiki_items.append(
                    {
                        "title": title,
                        "path": path,
                        "url": url,
                        "content": content,
                    }
                )

                if len(wiki_items) >= top_k:
                    return wiki_items

        return wiki_items
    except Exception as exc:  # pragma: no cover - runtime env dependency
        print(f"[WikiIngest] Full backlog fetch failed: {exc}")
        return []


async def ingest_wiki():
    """
    Fetch a broader wiki backlog from Azure DevOps and embed them into the local vector index,
    and optionally sync them into Azure AI Search.
    """
    print("📘 Starting wiki ingestion from Azure DevOps...")

    try:
        connector = AzureDevOpsConnector()
        local_service = LocalVectorSearchService()

        if local_service.enabled:
            print("✅ Local vector search enabled — embeddings will be persisted locally.")
        else:
            print(f"⚠️  Local vector search disabled: {local_service.init_error}")

        if settings.azure_search_enabled:
            print(f"✅ Azure AI Search enabled — index '{settings.azure_search_index_name}' will receive wiki documents.")
        else:
            print("⚠️  Azure AI Search not configured — only local indexing will run.")

        # Keep the old variable name so the rest of the script is unchanged.
        vector_service = local_service

        print("  🔎 Fetching the broader Azure DevOps wiki backlog (not limited to a few hard-coded terms)...")
        all_wiki_pages = await _fetch_full_wiki_backlog(connector, top_k=250)
        print(f"     ✓ Found {len(all_wiki_pages)} wiki pages in the backlog")

        print(f"\n✅ Total wiki pages ingested: {len(all_wiki_pages)}")

        indexed_count = vector_service.index_wiki_pages(all_wiki_pages)
        print(f"📦 Indexed {indexed_count} new wiki page(s) in local vector store")

        azure_indexed_count = await _ingest_to_azure_ai_search(all_wiki_pages)
        print(f"📦 Azure AI Search upload summary: {azure_indexed_count} document(s)")

        if all_wiki_pages:
            print("\n📌 Sample wiki page:")
            page = all_wiki_pages[0]
            print(f"   Title: {page['title']}")
            print(f"   Path: {page['path']}")

    except Exception as e:
        print(f"❌ Error during wiki ingestion: {str(e)}")
        print("Make sure your Azure DevOps credentials are set in .env")


if __name__ == "__main__":
    asyncio.run(ingest_wiki())