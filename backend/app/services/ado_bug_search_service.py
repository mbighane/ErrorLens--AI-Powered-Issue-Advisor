from typing import List, Union
from ..schemas.issue_schemas import BugResult
from .hybrid_bug_search_service import HybridBugSearchService


class ADOBugSearchService:
    """
    Main bug search service for Azure DevOps using Hybrid Search.
    
    Delegates to HybridBugSearchService which combines:
    - Semantic search (vector embeddings)
    - Exact match search (keyword/theme detection)
    """
    
    def __init__(self):
        self.hybrid_service = HybridBugSearchService()
        self.local_vector_service = self.hybrid_service.local_vector_service

    async def search_similar_bugs(self, query: str, top_k: int = 5) -> Union[List[BugResult], str]:
        """
        Search for similar issues in Azure DevOps using HYBRID search.
        
        Hybrid Search Strategy:
          1. Semantic Search (parallel): OpenAI embeddings + cosine similarity
          2. Exact Match Search (parallel): Keyword/theme matching via WIQL
          3. Merge & Rank: Combined scoring with RRF + weighted fusion
          
        Benefits:
          - Captures both semantic understanding and lexical precision
          - More robust to embedding quality issues
          - Finds conceptually similar bugs AND exact keyword matches
          - Adaptive: weights can be tuned per deployment
          
        Fallback:
          - If both searches fail, returns "no match" sentinel
        """
        try:
            # Use hybrid search combining semantic + exact match
            bugs = await self.hybrid_service.search_bugs_hybrid(query, top_k)
            
            if isinstance(bugs, str) and bugs == "no match":
                return "no match"
            
            if not bugs:
                return "no match"
            
            print(f"[ADOBugSearchService] Hybrid search returned {len(bugs)} result(s)")
            return self._build_final_results(bugs)
            
        except Exception as exc:
            print(f"[ADOBugSearchService] Hybrid search failed: {exc}")
            print("[ADOBugSearchService] Falling back to semantic-only search...")
            
            # Fallback to semantic search only
            try:
                bugs = await self.hybrid_service._semantic_search(query, top_k)
                if isinstance(bugs, str) and bugs == "no match":
                    return "no match"
                if not bugs:
                    return "no match"
                return self._build_final_results(bugs)
            except Exception as exc2:
                print(f"[ADOBugSearchService] Fallback search also failed: {exc2}")
                return "no match"
    
    def _build_final_results(self, bugs: Union[List[BugResult], List]) -> List[BugResult]:
        """Ensure results are BugResult objects."""
        if not bugs:
            return []
        if isinstance(bugs[0], BugResult):
            return bugs
        return bugs  # Already processed by hybrid service

