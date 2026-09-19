"""
Hybrid Bug Search Service
Combines semantic search (vector embeddings) + exact match search (keyword/text-based)
for comprehensive bug discovery.

Strategy:
  1. Run semantic search (vector similarity)
  2. Run exact match search (keyword matching, title overlap)
  3. Merge results using Reciprocal Rank Fusion (RRF) + weighted fusion
  4. Return combined ranked results
"""

import asyncio
import re
from typing import List, Dict, Any, Union, Tuple
from ..schemas.issue_schemas import BugResult
from .local_vector_search_service import LocalVectorSearchService
from .azure_ai_search_service import AzureAISearchService
from .azure_devops_connector import AzureDevOpsConnector
from ..config import settings


class HybridBugSearchService:
    """
    Hybrid search combining semantic (vector) and exact match (keyword) approaches.
    
    Scoring Strategy:
    - Semantic Score: cosine similarity from vector embedding (0.0-1.0)
    - Exact Match Score: calculated from keyword overlap, title match, theme detection (0.0-1.0)
    - Combined Score: 0.6 * semantic_score + 0.4 * exact_match_score
    
    Why hybrid?
    - Semantic alone: misses exact keyword matches, sensitive to embedding quality
    - Exact match alone: misses conceptually similar bugs with different wording
    - Hybrid: captures both lexical precision and semantic understanding
    """

    def __init__(self):
        self.local_vector_service = LocalVectorSearchService()
        self.azure_ai_search_service = AzureAISearchService()
        self.connector = AzureDevOpsConnector()

        # Tuning parameters
        self.SEMANTIC_WEIGHT = 0.6
        self.EXACT_MATCH_WEIGHT = 0.4
        self.RRF_K = 60  # reciprocal rank fusion smoothing factor

    async def search_bugs_hybrid(self, query: str, top_k: int = 5) -> Union[List[BugResult], str]:
        """
        Execute hybrid search: semantic + exact match in parallel, merge results.
        
        Args:
            query: User's bug query
            top_k: Number of top results to return
            
        Returns:
            List of BugResult sorted by combined score, or "no match" sentinel
        """
        # 1. Run semantic and exact match searches in parallel
        semantic_results, exact_match_results = await asyncio.gather(
            self._semantic_search(query, top_k=top_k * 2),  # Get more candidates for merging
            self._exact_match_search(query, top_k=top_k * 2),
            return_exceptions=True
        )

        # Handle exceptions
        if isinstance(semantic_results, Exception):
            print(f"[HybridSearch] Semantic search failed: {semantic_results}")
            semantic_results = []
        if isinstance(exact_match_results, Exception):
            print(f"[HybridSearch] Exact match search failed: {exact_match_results}")
            exact_match_results = []

        if isinstance(semantic_results, str) and semantic_results == "no match":
            semantic_results = []
        if isinstance(exact_match_results, str) and exact_match_results == "no match":
            exact_match_results = []

        # 2. Merge results using RRF + weighted scoring
        merged_bugs = self._merge_and_rank_results(
            semantic_results, exact_match_results, query
        )

        # 3. Filter by confidence threshold
        filtered_bugs = self._filter_by_threshold(merged_bugs, query)

        if not filtered_bugs:
            print("[HybridSearch] No bugs met similarity threshold; returning no match")
            return "no match"

        # 4. Index newly discovered bugs for future queries
        await self._lazy_index_bugs(filtered_bugs)

        # 5. Build and return BugResult objects
        return self._build_bug_results(filtered_bugs[:top_k])

    async def _semantic_search(self, query: str, top_k: int = 10) -> Union[List[Dict[str, Any]], str]:
        """
        Semantic search using Azure AI Search when configured, otherwise local vector fallback.
        
        Returns:
            List of bugs with 'similarity_score' field, or "no match" sentinel
        """
        bugs = []

        if settings.azure_search_enabled and self.azure_ai_search_service.enabled:
            try:
                bugs = self.azure_ai_search_service.search(query, top_k)
                if bugs:
                    print(f"[HybridSearch] Semantic: Azure AI Search returned {len(bugs)} bug(s)")
                    return bugs
            except Exception as exc:
                print(f"[HybridSearch] Semantic: Azure AI Search failed: {exc}")
                bugs = []

        if self.local_vector_service.enabled and self.local_vector_service.has_bugs_indexed():
            try:
                bugs = self.local_vector_service.search_bugs(query, top_k)
                if bugs:
                    print(f"[HybridSearch] Semantic: Local index returned {len(bugs)} bug(s)")
                    bugs = self.local_vector_service.rescore_bugs_from_search_results(query, bugs)
                    print(f"[HybridSearch] Semantic: Two-pass re-score applied to {len(bugs)} bug(s)")
            except Exception as exc:
                print(f"[HybridSearch] Semantic: Local search failed: {exc}")
                bugs = []

        return bugs if bugs else "no match"

    async def _exact_match_search(self, query: str, top_k: int = 10) -> Union[List[Dict[str, Any]], str]:
        """
        Exact match search using keyword/theme detection.
        Falls back to ADO WIQL search.
        
        Returns:
            List of bugs with 'exact_match_score' field, or "no match" sentinel
        """
        try:
            # Use ADO WIQL for keyword/theme-based search
            bugs = await self.connector.search_bugs(query, top_k)
            
            if bugs:
                # Add exact match scoring to each bug
                for bug in bugs:
                    exact_score = self._calculate_exact_match_score(query, bug)
                    bug["exact_match_score"] = exact_score
                print(f"[HybridSearch] Exact match: WIQL returned {len(bugs)} bug(s)")
                return bugs
            else:
                return "no match"
        except Exception as exc:
            print(f"[HybridSearch] Exact match search failed: {exc}")
            return "no match"

    def _calculate_exact_match_score(self, query: str, bug: Dict[str, Any]) -> float:
        """
        Calculate exact match score based on keyword overlap, title match, and theme detection.
        
        Score components:
        - Title exact match: 1.0
        - Title contains query: 0.8
        - Title token overlap: 0.3-0.7 based on ratio
        - Description keyword match: 0.2-0.5
        """
        score = 0.0

        # Normalize text
        query_norm = self._normalize_text(query)
        title = str(bug.get("title", "")).lower()
        description = str(bug.get("description", "")).lower()

        # 1. Title exact match (highest priority)
        if query_norm == self._normalize_text(title):
            return 1.0

        # 2. Title contains query
        if query_norm in self._normalize_text(title):
            score += 0.8
        elif self._normalize_text(title) in query_norm:
            score += 0.6

        # 3. Token overlap in title
        query_tokens = set(re.findall(r"\b[a-zA-Z0-9]+\b", query.lower()))
        title_tokens = set(re.findall(r"\b[a-zA-Z0-9]+\b", title))

        if query_tokens:
            common_tokens = query_tokens & title_tokens
            token_overlap = len(common_tokens) / len(query_tokens)
            score += token_overlap * 0.5  # 0.0-0.5 points

        # 4. Description keyword match
        if query_norm in description:
            score += 0.5
        else:
            # Count keyword occurrences in description
            keywords = query_tokens
            keyword_count = sum(1 for kw in keywords if kw in description)
            if keywords:
                keyword_ratio = keyword_count / len(keywords)
                score += keyword_ratio * 0.3

        # Cap at 1.0
        return min(score, 1.0)

    def _merge_and_rank_results(
        self,
        semantic_bugs: List[Dict[str, Any]],
        exact_match_bugs: List[Dict[str, Any]],
        query: str,
    ) -> List[Dict[str, Any]]:
        """
        Merge semantic and exact match results using Reciprocal Rank Fusion.
        
        Algorithm:
        1. Rank each result set by score (1st place = highest score)
        2. Calculate RRF score: sum of 1/(k + rank) for each result
        3. Apply weighted combination: 0.6*semantic + 0.4*exact_match
        4. Sort by combined score
        """
        bug_map: Dict[str, Dict[str, Any]] = {}

        # Process semantic results
        for rank, bug in enumerate(semantic_bugs, 1):
            bug_id = bug.get("id")
            if bug_id not in bug_map:
                bug_map[bug_id] = {}
            
            bug_map[bug_id].update(bug)
            semantic_score = float(bug.get("similarity_score", 0.0))
            rrf_semantic = 1.0 / (self.RRF_K + rank)
            
            bug_map[bug_id]["_semantic_score"] = semantic_score
            bug_map[bug_id]["_rrf_semantic"] = rrf_semantic

        # Process exact match results
        for rank, bug in enumerate(exact_match_bugs, 1):
            bug_id = bug.get("id")
            if bug_id not in bug_map:
                bug_map[bug_id] = {}
            
            bug_map[bug_id].update(bug)
            exact_score = float(bug.get("exact_match_score", 0.0))
            rrf_exact = 1.0 / (self.RRF_K + rank)
            
            bug_map[bug_id]["_exact_match_score"] = exact_score
            bug_map[bug_id]["_rrf_exact"] = rrf_exact

        # Calculate combined scores
        for bug_id, bug in bug_map.items():
            semantic_score = bug.get("_semantic_score", 0.0)
            exact_score = bug.get("_exact_match_score", 0.0)
            rrf_semantic = bug.get("_rrf_semantic", 0.0)
            rrf_exact = bug.get("_rrf_exact", 0.0)

            # Hybrid score: weighted average of both approaches
            hybrid_score = (
                self.SEMANTIC_WEIGHT * semantic_score +
                self.EXACT_MATCH_WEIGHT * exact_score
            )

            # RRF fusion score (gives ranking bonus)
            rrf_score = rrf_semantic + rrf_exact

            bug["similarity_score"] = hybrid_score
            bug["_rrf_score"] = rrf_score

        # Sort by hybrid score (primary) and RRF score (tiebreaker)
        ranked_bugs = sorted(
            bug_map.values(),
            key=lambda b: (b.get("similarity_score", 0.0), b.get("_rrf_score", 0.0)),
            reverse=True
        )

        print(f"[HybridSearch] Merged {len(ranked_bugs)} unique bugs from both approaches")
        return ranked_bugs

    def _filter_by_threshold(
        self,
        bugs: List[Dict[str, Any]],
        query: str,
    ) -> List[Dict[str, Any]]:
        """
        Filter results by similarity threshold and title overlap.
        Ensures high-confidence matches.
        """
        filtered = []

        for bug in bugs:
            score = float(bug.get("similarity_score", 0.0))
            title = str(bug.get("title", ""))
            title_overlap = self._title_overlap_score(query, title)

            # Accept if: title exact match, OR meets both thresholds
            title_exact = (
                self._normalize_text(query) == self._normalize_text(title)
                or self._normalize_text(query) in self._normalize_text(title)
                or self._normalize_text(title) in self._normalize_text(query)
            )

            if title_exact or (
                score >= settings.search_similarity_threshold
                and title_overlap >= 0.05
            ):
                filtered.append(bug)

        return filtered

    def _title_overlap_score(self, query: str, title: str) -> float:
        """Calculate token overlap between query and title."""
        if not query or not title:
            return 0.0

        query_norm = self._normalize_text(query)
        title_norm = self._normalize_text(title)

        if query_norm == title_norm:
            return 1.0
        if query_norm in title_norm or title_norm in query_norm:
            return 0.75

        query_tokens = set(re.findall(r"\b[a-zA-Z0-9]+\b", query.lower()))
        title_tokens = set(re.findall(r"\b[a-zA-Z0-9]+\b", title.lower()))

        if not query_tokens:
            return 0.0

        common = query_tokens & title_tokens
        return len(common) / len(query_tokens)

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    async def _lazy_index_bugs(self, bugs: List[Dict[str, Any]]) -> None:
        """
        Index newly discovered bugs so subsequent queries hit vector search.
        Runs in background without blocking response.
        """
        if not bugs or not self.local_vector_service.enabled:
            return

        try:
            newly_indexed = self.local_vector_service.index_bugs(bugs)
            if newly_indexed:
                print(f"[HybridSearch] Indexed {newly_indexed} new bug(s) locally")
        except Exception as exc:
            print(f"[HybridSearch] Local indexing failed: {exc}")

    def _build_bug_results(self, bugs: List[Dict[str, Any]]) -> List[BugResult]:
        """Convert merged bug dicts to BugResult objects."""
        results = []

        for bug in bugs:
            description = bug.get("description", "")
            root_cause_analysis = bug.get("root_cause_analysis", "")
            suggested_fix = bug.get("suggested_fix", "")

            combined_description = description
            if root_cause_analysis:
                combined_description = (
                    f"{description}\n\nRoot Cause Analysis:\n{root_cause_analysis}"
                    if description
                    else f"Root Cause Analysis:\n{root_cause_analysis}"
                )

            results.append(
                BugResult(
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
                        "exact_match_score": bug.get("exact_match_score", 0.0),
                        "rrf_score": bug.get("_rrf_score", 0.0),
                    },
                )
            )

        return results
