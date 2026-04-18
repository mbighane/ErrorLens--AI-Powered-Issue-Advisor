from __future__ import annotations

from typing import Any, Dict, List, Optional

from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.redis import RedisVectorStore
from redisvl.schema import IndexSchema

from ..config import settings


class RedisVectorSearchService:
    """Redis-backed vector indexing and retrieval for bugs and wiki pages."""

    def __init__(self):
        self.enabled = False
        self.init_error = ""
        self.bug_store: Optional[RedisVectorStore] = None
        self.wiki_store: Optional[RedisVectorStore] = None
        self.embedding_model: Optional[OpenAIEmbedding] = None

        try:
            redis_url = f"redis://{settings.redis_host}:{settings.redis_port}"
            self.bug_store = RedisVectorStore(
                schema=self._build_schema("errorlens_bugs", "errorlens:bugs"),
                redis_url=redis_url,
            )
            self.wiki_store = RedisVectorStore(
                schema=self._build_schema("errorlens_wiki", "errorlens:wiki"),
                redis_url=redis_url,
            )
            self.embedding_model = OpenAIEmbedding(api_key=settings.openai_api_key)
            Settings.embed_model = self.embedding_model
            self.enabled = True
        except Exception as exc:
            self.init_error = str(exc)

    @staticmethod
    def _build_schema(index_name: str, prefix: str) -> IndexSchema:
        return IndexSchema.from_dict(
            {
                "index": {
                    "name": index_name,
                    "prefix": prefix,
                    "key_separator": ":",
                    "storage_type": "hash",
                },
                "fields": [
                    {"type": "tag", "name": "id", "attrs": {"sortable": False}},
                    {"type": "tag", "name": "doc_id", "attrs": {"sortable": False}},
                    {"type": "text", "name": "text", "attrs": {"weight": 1.0}},
                    {
                        "type": "vector",
                        "name": "vector",
                        "attrs": {
                            "dims": 1536,
                            "algorithm": "flat",
                            "distance_metric": "cosine",
                        },
                    },
                ],
            }
        )

    def _upsert_documents(self, docs: List[Document], vector_store: RedisVectorStore) -> None:
        if not self.enabled or not docs:
            return

        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        VectorStoreIndex.from_documents(
            docs,
            storage_context=storage_context,
            embed_model=self.embedding_model,
            show_progress=False,
        )

    def _search_documents(
        self,
        query: str,
        top_k: int,
        vector_store: RedisVectorStore,
    ) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []

        index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            embed_model=self.embedding_model,
        )
        retriever = index.as_retriever(similarity_top_k=top_k)

        results: List[Dict[str, Any]] = []
        for node_with_score in retriever.retrieve(query):
            metadata = node_with_score.node.metadata or {}
            results.append(
                {
                    **metadata,
                    "similarity_score": float(node_with_score.score or 0.0),
                    "text": node_with_score.node.get_content(),
                }
            )

        return results

    def index_bugs(self, bugs: List[Dict[str, Any]]) -> int:
        if not self.enabled:
            return 0

        docs: List[Document] = []
        for bug in bugs:
            root_cause = bug.get("root_cause_analysis", "")
            text_parts = [
                f"Title: {bug.get('title', '')}",
                f"Description: {bug.get('description', '')}",
                f"Root Cause Analysis: {root_cause}",
            ]
            text = "\n".join(part for part in text_parts if part.strip())
            metadata = {
                "id": bug.get("id", ""),
                "title": bug.get("title", ""),
                "description": bug.get("description", ""),
                "root_cause_analysis": root_cause,
                "state": bug.get("state", ""),
                "assigned_to": bug.get("assigned_to", ""),
                "url": bug.get("url", ""),
                "work_item_type": bug.get("work_item_type", "Issue"),
                "source": "azure_devops",
            }
            docs.append(
                Document(
                    id_=f"bug-{bug.get('id', len(docs))}",
                    text=text,
                    metadata=metadata,
                )
            )

        if self.bug_store is None:
            return 0
        self._upsert_documents(docs, self.bug_store)
        return len(docs)

    def search_bugs(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        if self.bug_store is None:
            return []
        return self._search_documents(query, top_k, self.bug_store)

    def index_wiki_pages(self, pages: List[Dict[str, Any]]) -> int:
        if not self.enabled:
            return 0

        docs: List[Document] = []
        for idx, page in enumerate(pages):
            text_parts = [
                f"Title: {page.get('title', '')}",
                f"Path: {page.get('path', '')}",
                f"Content: {page.get('content', '')}",
            ]
            text = "\n".join(part for part in text_parts if part.strip())
            metadata = {
                "title": page.get("title", ""),
                "content": page.get("content", ""),
                "path": page.get("path", ""),
                "url": page.get("url", ""),
                "source": "azure_devops_wiki",
            }
            page_id = page.get("id") or page.get("path") or str(idx)
            docs.append(Document(id_=f"wiki-{page_id}", text=text, metadata=metadata))

        if self.wiki_store is None:
            return 0
        self._upsert_documents(docs, self.wiki_store)
        return len(docs)

    def search_wiki_pages(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        if self.wiki_store is None:
            return []
        return self._search_documents(query, top_k, self.wiki_store)
