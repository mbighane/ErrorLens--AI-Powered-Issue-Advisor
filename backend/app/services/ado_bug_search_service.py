from typing import List
from ..schemas.issue_schemas import BugResult
from .azure_devops_connector import AzureDevOpsConnector
from .redis_vector_search_service import RedisVectorSearchService
from .local_vector_search_service import LocalVectorSearchService

class ADOBugSearchService:
    def __init__(self):
        self.connector = AzureDevOpsConnector()
        self.local_vector_service = LocalVectorSearchService()
        self.redis_vector_service = RedisVectorSearchService()

    async def search_similar_bugs(self, query: str, top_k: int = 5) -> List[BugResult]:
        """
        Search for similar issues in Azure DevOps.
        Priority:
          1. Local vector index (OpenAI embeddings + numpy cosine similarity)
          2. Redis vector store (requires Redis Stack)
          3. ADO WIQL keyword search + theme-based scoring (always available)
        Bugs fetched from ADO are automatically indexed locally for future queries.
        """
        bugs = []

        # 1. Local vector search — preferred when index has been seeded.
        if self.local_vector_service.enabled and self.local_vector_service.has_bugs_indexed():
            try:
                bugs = self.local_vector_service.search_bugs(query, top_k)
                if bugs:
                    print(f"[VectorSearch] Local index returned {len(bugs)} bug(s) for query.")
                    # Two-pass rescore: use initial results' content to enrich query, then rescore.
                    bugs = self.local_vector_service.rescore_bugs_from_search_results(query, bugs)
                    print(f"[VectorSearch] Two-pass re-score applied to {len(bugs)} local bug(s).")
            except Exception as exc:
                print(f"[VectorSearch] Local bug search failed: {exc}")
                bugs = []

        # 2. Redis vector search fallback.
        if not bugs:
            try:
                bugs = self.redis_vector_service.search_bugs(query, top_k)
            except Exception:
                bugs = []

        # 3. ADO WIQL + theme-based scoring fallback.
        if not bugs:
            bugs = await self.connector.search_bugs(query, top_k)
            # Re-score ADO results using two-pass semantic rescoring:
            # Pass 1 finds the closest bugs, their content enriches the query,
            # Pass 2 re-scores all bugs with the enriched query.
            if bugs and self.local_vector_service.enabled:
                try:
                    bugs = self.local_vector_service.rescore_bugs_from_search_results(query, bugs)
                    print(f"[VectorSearch] Two-pass re-scored {len(bugs)} ADO bug(s).")
                except Exception as exc:
                    print(f"[VectorSearch] Two-pass re-scoring failed: {exc}")
            # Lazily index fetched bugs so subsequent queries hit vector search.
            if bugs:
                try:
                    newly_indexed = self.local_vector_service.index_bugs(bugs)
                    if newly_indexed:
                        print(f"[VectorSearch] Indexed {newly_indexed} new bug(s) into local vector store.")
                except Exception as exc:
                    print(f"[VectorSearch] Local bug indexing failed: {exc}")
                try:
                    self.redis_vector_service.index_bugs(bugs)
                except Exception:
                    pass
        
        bug_results = []
        for bug in bugs:
            description = bug.get("description", "")
            root_cause_analysis = bug.get("root_cause_analysis", "")
            suggested_fix = bug.get("suggested_fix", "")
            combined_description = description
            if root_cause_analysis:
                combined_description = f"{description}\n\nRoot Cause Analysis:\n{root_cause_analysis}" if description else f"Root Cause Analysis:\n{root_cause_analysis}"

            bug_results.append(BugResult(
                id=bug["id"],
                title=bug["title"],
                description=combined_description,
                state=bug.get("state"),
                assigned_to=bug.get("assigned_to"),
                url=bug.get("url"),
                similarity_score=bug.get("similarity_score", 0.0),
                metadata={
                    "root_cause_analysis": root_cause_analysis,
                    "suggested_fix": suggested_fix,
                    "work_item_type": "Issue",
                },
            ))
        
        return bug_results
