from __future__ import annotations

from typing import Any, Dict, List, Optional

from openai import AzureOpenAI

from ..config import settings
from ..providers.factory import create_embedding_provider
from ..providers.interfaces import IEmbeddingProvider


class AzureAISearchService:
    """Azure AI Search wrapper used as the managed retrieval layer when configured."""

    def __init__(self) -> None:
        self.enabled = False
        self.init_error = ""
        self._client = None
        self._embedding_provider: Optional[IEmbeddingProvider] = None

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
            self._embedding_provider = create_embedding_provider()
            self.enabled = True
        except Exception as exc:  # pragma: no cover - guarded runtime import
            self.enabled = False
            self.init_error = str(exc)
            print(f"[AzureAISearchService] init failed: {exc}")

    def search(
        self,
        query: str,
        top_k: int = 5,
        category: str | None = None,
    ) -> List[Dict[str, Any]]:
        """Execute a managed Azure AI Search query and normalize results."""
        if not self.enabled or self._client is None:
            return []

        try:
            expanded_query = self._expand_query(query)
            semantic_profile = (settings.azure_search_semantic_configuration or "default").strip()
            selected_fields = [
                field.strip()
                for field in settings.azure_search_semantic_fields.split(",")
                if field.strip()
            ]
            if not selected_fields:
                raise ValueError("AZURE_SEARCH_SEMANTIC_FIELDS is empty")

            search_kwargs: Dict[str, Any] = {
                "search_text": expanded_query,
                "top": top_k,
                "select": ",".join(selected_fields),
            }
            if category:
                search_kwargs["filter"] = f"category eq '{category}'"
            if self._embedding_provider is None:
                raise RuntimeError("Azure embedding provider is not initialized")
            query_vector = self._embedding_provider.embed_texts([expanded_query])[0]
            from azure.search.documents.models import VectorizedQuery

            search_kwargs["vector_queries"] = [
                VectorizedQuery(
                    vector=query_vector,
                    k_nearest_neighbors=top_k,
                    fields="contentVector",
                )
            ]
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
                reranker_score = hit.get("@search.reranker_score")
                try:
                    if reranker_score is not None:
                        max_score = max(settings.azure_semantic_reranker_max_score, 1.0)
                        similarity_score = min(max(float(reranker_score) / max_score, 0.0), 1.0)
                    else:
                        similarity_score = min(max(float(score), 0.0), 1.0)
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
                        "azure_search_score": score,
                        "azure_reranker_score": reranker_score,
                    }
                )

            normalized = [
                item for item in normalized
                if item.get("azure_reranker_score") is None
                or float(item["azure_reranker_score"]) >= settings.azure_semantic_min_reranker_score
            ]
            return normalized
        except Exception as exc:  # pragma: no cover - runtime dependency path
            print(f"[AzureAISearchService] search failed: {exc}")
            return []

    @staticmethod
    def _expand_query(query: str) -> str:
        """Expand a short issue description before Azure keyword/vector retrieval."""
        if not settings.azure_query_expansion_enabled:
            return query

        try:
            if settings.use_azure_openai:
                client = AzureOpenAI(
                    api_key=settings.azure_openai_api_key,
                    api_version=settings.azure_openai_api_version,
                    azure_endpoint=settings.azure_openai_endpoint,
                )
                model = settings.azure_openai_chat_deployment
            else:
                return query

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a software issue search assistant. Expand the user's issue "
                            "into a concise technical search query using synonyms and related UI, "
                            "API, database, integration, and troubleshooting terms when relevant. "
                            "Preserve the original meaning. Return only the expanded query, under 40 words."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                temperature=settings.query_expansion_temperature,
                max_tokens=settings.query_expansion_max_tokens,
            )
            expanded = (response.choices[0].message.content or "").strip()
            if expanded:
                print(f"[AzureSearch] Query expanded: '{query}' -> '{expanded}'")
                return expanded
        except Exception as exc:
            print(f"[AzureSearch] Query expansion failed, using original query: {exc}")

        return query
