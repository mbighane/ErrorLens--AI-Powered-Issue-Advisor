from typing import List, Union
from ..schemas.issue_schemas import WikiResult
from .azure_devops_connector import AzureDevOpsConnector
from .local_vector_search_service import LocalVectorSearchService
from .azure_ai_search_service import AzureAISearchService
from ..config import settings

class ADOWikiSearchService:
    def __init__(self):
        self.connector = AzureDevOpsConnector()
        self.local_vector_service = (
            LocalVectorSearchService() if settings.is_on_prem_deployment else None
        )
        self.azure_ai_search_service = AzureAISearchService()

    async def search_wiki_pages(self, query: str, top_k: int = 10) -> Union[List[WikiResult], str]:
        """
        Search for relevant wiki pages in Azure DevOps.
        Priority:
          1. Azure AI Search (managed semantic retrieval when configured)
          2. Local vector index (Ollama + numpy cosine similarity)
          3. ADO git-based wiki search (always available)
        Wiki pages fetched from ADO are automatically indexed locally for future queries.
        """
        wiki_pages = []

        # 1. Azure AI Search — preferred when configured.
        if settings.azure_search_enabled and self.azure_ai_search_service.enabled:
            try:
                wiki_pages = self.azure_ai_search_service.search(query, top_k, category="wiki")
                if wiki_pages:
                    wiki_pages = [max(wiki_pages, key=lambda p: p.get("similarity_score", 0))]
                    wiki_pages[0].setdefault("source", "azure_ai_search")
                    print(f"[VectorSearch] Azure AI Search returned top-1 wiki result (score={wiki_pages[0].get('similarity_score', 0):.4f}) for query.")
            except Exception as exc:
                print(f"[VectorSearch] Azure AI Search wiki search failed: {exc}")
                wiki_pages = []

        # 2. Local vector search — preferred when index has been seeded.
        if (
            settings.is_on_prem_deployment
            and self.local_vector_service is not None
            and self.local_vector_service.has_wiki_indexed()
        ):
            try:
                wiki_pages = self.local_vector_service.search_wiki_pages(query, top_k)
                # Keep only the highest-scoring result to avoid surfacing loosely
                # related sections from the same parent page.
                if wiki_pages:
                    wiki_pages = [max(wiki_pages, key=lambda p: p.get("similarity_score", 0))]
                    wiki_pages[0].setdefault("source", "local_vector_index")
                    print(f"[VectorSearch] Local index returned top-1 wiki section (score={wiki_pages[0].get('similarity_score', 0):.4f}) for query.")
            except Exception as exc:
                print(f"[VectorSearch] Local wiki search failed: {exc}")
                wiki_pages = []

        # 3. ADO git-based wiki search fallback.
        if not wiki_pages:
            if not hasattr(self.connector, "search_wiki_pages"):
                return "no match"
            wiki_pages = await self.connector.search_wiki_pages(query, top_k)
            # Lazily index fetched pages so subsequent queries hit vector search.
            if wiki_pages and settings.is_on_prem_deployment and self.local_vector_service is not None:
                try:
                    newly_indexed = self.local_vector_service.index_wiki_pages(wiki_pages)
                    if newly_indexed:
                        print(f"[VectorSearch] Indexed {newly_indexed} new wiki page(s) into local vector store.")
                except Exception as exc:
                    print(f"[VectorSearch] Local wiki indexing failed: {exc}")
        
        # If no candidate wiki pages or top similarity below threshold, return sentinel
        if not wiki_pages:
            return "no match"
        best_score = max((p.get("similarity_score", 0.0) for p in wiki_pages), default=0.0)
        if best_score < settings.search_similarity_threshold:
            print(f"[VectorSearch] Best wiki similarity {best_score:.4f} below threshold {settings.search_similarity_threshold:.4f}; returning no match")
            return "no match"

        wiki_results = []
        for page in wiki_pages:
            # Sanitise content: re-encode as UTF-8 replacing any unmappable chars
            raw_content = page.get("content", page.get("text", "")) or ""
            safe_content = raw_content.encode("utf-8", errors="replace").decode("utf-8")
            wiki_results.append(WikiResult(
                title=page["title"],
                content=safe_content,
                similarity_score=page.get("similarity_score", 0.8),
                source=page.get("source", "local_vector_index"),
                path=page.get("path"),
                url=page.get("url"),
            ))
        
        return wiki_results