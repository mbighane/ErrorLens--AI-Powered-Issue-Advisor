from __future__ import annotations

from typing import Any, Dict, List

from ..config import settings


class AzureAISearchService:
    """Azure AI Search wrapper used as the managed retrieval layer when configured."""

    def __init__(self) -> None:
        self.enabled = False
        self.init_error = ""
        self._client = None

        if not settings.azure_search_enabled:
            return

        try:
            from azure.core.credentials import AzureKeyCredential
            from azure.search.documents import SearchClient

            self._client = SearchClient(
                endpoint=settings.azure_search_endpoint,
                index_name=settings.azure_search_index_name,
                credential=AzureKeyCredential(settings.azure_search_api_key),
            )
            self.enabled = True
        except Exception as exc:  # pragma: no cover - guarded runtime import
            self.enabled = False
            self.init_error = str(exc)
            print(f"[AzureAISearchService] init failed: {exc}")

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Execute a managed Azure AI Search query and normalize results."""
        if not self.enabled or self._client is None:
            return []

        try:
            semantic_profile = (settings.azure_search_semantic_configuration or "default").strip()
            selected_fields = [
                field.strip()
                for field in settings.azure_search_semantic_fields.split(",")
                if field.strip()
            ]
            if not selected_fields:
                raise ValueError("AZURE_SEARCH_SEMANTIC_FIELDS is empty")

            search_kwargs: Dict[str, Any] = {
                "search_text": query,
                "top": top_k,
                "select": ",".join(selected_fields),
            }

            if settings.azure_search_use_semantic_search:
                if not semantic_profile:
                    raise ValueError("AZURE_SEARCH_SEMANTIC_CONFIGURATION is not configured")
                search_kwargs.update(
                    {
                        "query_type": "semantic",
                        "semantic_configuration_name": semantic_profile,
                    }
                )
            else:
                search_kwargs["query_type"] = "simple"

            results = self._client.search(**search_kwargs)

            normalized: List[Dict[str, Any]] = []
            for hit in results:
                score = hit.get("@search.score", 0.0)
                try:
                    similarity_score = float(score)
                except (TypeError, ValueError):
                    similarity_score = 0.0

                description = hit.get("description") or hit.get("content") or ""
                normalized.append(
                    {
                        "id": hit.get("id", str(len(normalized))),
                        "title": hit.get("title", ""),
                        "description": description,
                        "content": hit.get("content", description),
                        "root_cause_analysis": hit.get("root_cause_analysis", ""),
                        "path": hit.get("path", ""),
                        "url": hit.get("url", ""),
                        "category": hit.get("category", ""),
                        "source": hit.get("source", "azure_ai_search"),
                        "similarity_score": similarity_score,
                    }
                )

            return normalized
        except Exception as exc:  # pragma: no cover - runtime dependency path
            print(f"[AzureAISearchService] search failed: {exc}")
            return []
