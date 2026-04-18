from typing import List
from ..schemas.issue_schemas import WikiResult
from .azure_devops_connector import AzureDevOpsConnector
from .redis_vector_search_service import RedisVectorSearchService
from .local_vector_search_service import LocalVectorSearchService

class ADOWikiSearchService:
    def __init__(self):
        self.connector = AzureDevOpsConnector()
        self.local_vector_service = LocalVectorSearchService()
        self.redis_vector_service = RedisVectorSearchService()

    async def search_wiki_pages(self, query: str, top_k: int = 5) -> List[WikiResult]:
        """
        Search for relevant wiki pages in Azure DevOps.
        Priority:
          1. Local vector index (OpenAI embeddings + numpy cosine similarity)
          2. Redis vector store (requires Redis Stack)
          3. ADO git-based wiki search (always available)
        Wiki pages fetched from ADO are automatically indexed locally for future queries.
        """
        wiki_pages = []

        # 1. Local vector search — preferred when index has been seeded.
        if self.local_vector_service.enabled and self.local_vector_service.has_wiki_indexed():
            try:
                wiki_pages = self.local_vector_service.search_wiki_pages(query, top_k)
                if wiki_pages:
                    print(f"[VectorSearch] Local index returned {len(wiki_pages)} wiki page(s) for query.")
            except Exception as exc:
                print(f"[VectorSearch] Local wiki search failed: {exc}")
                wiki_pages = []

        # 2. Redis vector search fallback.
        if not wiki_pages:
            try:
                wiki_pages = self.redis_vector_service.search_wiki_pages(query, top_k)
            except Exception:
                wiki_pages = []

        # 3. ADO git-based wiki search fallback.
        if not wiki_pages:
            wiki_pages = await self.connector.search_wiki_pages(query, top_k)
            # Lazily index fetched pages so subsequent queries hit vector search.
            if wiki_pages:
                try:
                    newly_indexed = self.local_vector_service.index_wiki_pages(wiki_pages)
                    if newly_indexed:
                        print(f"[VectorSearch] Indexed {newly_indexed} new wiki page(s) into local vector store.")
                except Exception as exc:
                    print(f"[VectorSearch] Local wiki indexing failed: {exc}")
                try:
                    self.redis_vector_service.index_wiki_pages(wiki_pages)
                except Exception:
                    pass
        
        wiki_results = []
        for page in wiki_pages:
            # Sanitise content: re-encode as UTF-8 replacing any unmappable chars
            raw_content = page.get("content", page.get("text", "")) or ""
            safe_content = raw_content.encode("utf-8", errors="replace").decode("utf-8")
            wiki_results.append(WikiResult(
                title=page["title"],
                content=safe_content,
                similarity_score=page.get("similarity_score", 0.8),
                path=page.get("path"),
                url=page.get("url"),
            ))
        
        return wiki_results