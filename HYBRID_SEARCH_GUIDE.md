# Hybrid Search Implementation Guide

## Overview

ErrorLens now uses **Hybrid Search** to combine semantic search (vector embeddings) with exact match search (keyword/theme detection) for more comprehensive bug discovery.

## Why Hybrid Search?

### Problems with Semantic-Only Search
- ❌ Depends heavily on embedding quality
- ❌ Misses exact keyword matches with low semantic similarity
- ❌ Performance degrades with out-of-domain queries
- ❌ Sensitive to query phrasing variations

### Problems with Exact Match-Only Search
- ❌ Misses conceptually similar bugs with different wording
- ❌ Cannot find bugs with synonym variations
- ❌ Limited to literal string matching
- ❌ Poor for fuzzy/approximate matching

### Hybrid Search Benefits ✅
- ✅ **Comprehensive Coverage**: Captures both semantic understanding AND lexical precision
- ✅ **Robust**: Falls back gracefully if one method fails
- ✅ **Adaptive**: Scoring weights can be tuned per deployment
- ✅ **Parallel Execution**: Both searches run simultaneously for speed
- ✅ **Intelligent Merging**: Uses Reciprocal Rank Fusion (RRF) to combine results

---

## Architecture

### Search Pipeline

```
User Query
    │
    ├──────────────────────────────┬──────────────────────────────┐
    │                              │                              │
    ▼                              ▼                              ▼
[SEMANTIC]                    [EXACT MATCH]                   [MERGE & RANK]
OpenAI Embeddings            Keyword/Theme Detection         RRF Scoring
+ Local Vector Index         + WIQL Search                   + Weighted Fusion
    │                              │                              │
    └──────────────────────────────┼──────────────────────────────┘
                                   │
                                   ▼
                           [THRESHOLD FILTER]
                           Confidence check
                                   │
                                   ▼
                            BugResult objects
```

### Services Involved

| Service | Purpose | Method |
|---------|---------|--------|
| `HybridBugSearchService` | Orchestrates hybrid search | `search_bugs_hybrid()` |
| `LocalVectorSearchService` | Semantic search (vector) | `search_bugs()` |
| `AzureDevOpsConnector` | Exact match search (keyword) | `search_bugs()` |
| `ADOBugSearchService` | Main entry point | `search_similar_bugs()` |

---

## Scoring Strategy

### 1. Semantic Score (0.0 - 1.0)
- **Source**: Cosine similarity from vector embeddings
- **Range**: 0 (no match) to 1 (perfect match)
- **Method**: 
  - Query expanded with technical synonyms via GPT
  - Converted to 1536-dimensional embedding
  - Cosine similarity computed against bug database

### 2. Exact Match Score (0.0 - 1.0)
- **Source**: Keyword overlap and title matching
- **Components**:
  - Title exact match: 1.0 points
  - Title contains query: 0.8 points
  - Title token overlap: 0.3-0.7 points (ratio-based)
  - Description keyword match: 0.2-0.5 points

### 3. Combined Hybrid Score
```
hybrid_score = (0.6 × semantic_score) + (0.4 × exact_match_score)
```

**Weighting Rationale**:
- Semantic (60%): Captures conceptual understanding
- Exact Match (40%): Ensures keyword precision
- Tunable: Edit `SEMANTIC_WEIGHT` and `EXACT_MATCH_WEIGHT` in `HybridBugSearchService`

### 4. Reciprocal Rank Fusion (RRF)
- Combines ranking from both methods
- Formula: `RRF_score = 1 / (K + rank)` where K=60
- Gives ranking bonus to high-ranked results in either method
- Acts as tiebreaker for equal hybrid scores

---

## Implementation Details

### File Structure
```
backend/app/services/
├── hybrid_bug_search_service.py    [NEW] Main hybrid search logic
├── ado_bug_search_service.py        [MODIFIED] Now delegates to hybrid
├── local_vector_search_service.py   [UNCHANGED] Semantic search provider
├── redis_vector_search_service.py   [UNCHANGED] Vector store fallback
└── azure_devops_connector.py        [UNCHANGED] WIQL/exact search provider
```

### Key Methods in HybridBugSearchService

#### `search_bugs_hybrid(query, top_k)`
Main entry point. Orchestrates the hybrid search workflow.

```python
async def search_bugs_hybrid(self, query: str, top_k: int = 5) -> Union[List[BugResult], str]:
    """Execute hybrid search: semantic + exact match in parallel, merge results."""
```

#### `_semantic_search(query, top_k)`
Runs vector-based semantic search.

```python
async def _semantic_search(self, query: str, top_k: int = 10) -> Union[List[Dict], str]:
    """Semantic search using vector embeddings (local or Redis fallback)."""
```

#### `_exact_match_search(query, top_k)`
Runs keyword/theme-based exact match search.

```python
async def _exact_match_search(self, query: str, top_k: int = 10) -> Union[List[Dict], str]:
    """Exact match search using keyword/theme detection."""
```

#### `_merge_and_rank_results(semantic_bugs, exact_match_bugs, query)`
Merges results using RRF and weighted scoring.

```python
def _merge_and_rank_results(
    self, semantic_bugs, exact_match_bugs, query
) -> List[Dict[str, Any]]:
    """Merge semantic and exact match results using RRF + weighted fusion."""
```

---

## Configuration

### Tuning Parameters

In `hybrid_bug_search_service.py`:

```python
# Scoring weights
self.SEMANTIC_WEIGHT = 0.6          # Semantic search weight
self.EXACT_MATCH_WEIGHT = 0.4       # Exact match weight

# RRF smoothing
self.RRF_K = 60                     # Reciprocal Rank Fusion parameter
```

### Per-Deployment Tuning

**For high precision (minimize false positives)**:
```python
SEMANTIC_WEIGHT = 0.7        # Trust embeddings more
EXACT_MATCH_WEIGHT = 0.3
```

**For high recall (find more potential matches)**:
```python
SEMANTIC_WEIGHT = 0.5        # Balance both approaches equally
EXACT_MATCH_WEIGHT = 0.5
```

**For keyword-focused (exact match priority)**:
```python
SEMANTIC_WEIGHT = 0.3
EXACT_MATCH_WEIGHT = 0.7     # Prioritize exact keywords
```

---

## Data Flow

### Example: Query "Memory leak in list processing"

```
INPUT: "Memory leak in list processing"
│
├─ [SEMANTIC SEARCH]
│  ├─ Expand: "Memory leak list processing memory management..."
│  ├─ Embed: OpenAI embedding (1536 dims)
│  ├─ Search: Local vector index
│  └─ Results: 
│     • Bug#123: "Out of memory in ArrayList.Add()" (score: 0.87)
│     • Bug#456: "Memory not freed after loop" (score: 0.79)
│
├─ [EXACT MATCH SEARCH]
│  ├─ Keywords: ["memory", "leak", "list", "processing"]
│  ├─ Search: WIQL + theme detection
│  └─ Results:
│     • Bug#456: "Memory not freed after loop" (score: 0.85)
│     • Bug#789: "List iteration memory issue" (score: 0.72)
│
├─ [MERGE & RANK]
│  ├─ Bug#456: hybrid = 0.6*0.79 + 0.4*0.85 = 0.814 ✓ Both matched
│  ├─ Bug#123: hybrid = 0.6*0.87 + 0.4*0.00 = 0.522 ✓ Semantic only
│  └─ Bug#789: hybrid = 0.6*0.00 + 0.4*0.72 = 0.288   Exact only
│
└─ OUTPUT (top-2):
   1. Bug#456 (0.814) ← Found by both methods
   2. Bug#123 (0.522) ← Found by semantic search
```

---

## Error Handling & Fallback

```python
try:
    # 1. Try hybrid search
    bugs = await hybrid_service.search_bugs_hybrid(query, top_k)
except Exception:
    # 2. Fallback to semantic-only search
    bugs = await hybrid_service._semantic_search(query, top_k)
except Exception:
    # 3. Return "no match" sentinel
    return "no match"
```

---

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Semantic search | ~200-500ms | Depends on index size |
| Exact match search | ~500-2000ms | WIQL API call to ADO |
| Merge & rank | ~10-50ms | Linear in result count |
| **Total (parallel)** | ~500-2000ms | Dominated by WIQL (parallel) |

**Optimization**: Parallel execution means total time ≈ max(semantic_time, exact_time), not sum.

---

## Testing

### Test Cases

1. **Semantic match only**: Query finds bugs via embeddings, not keywords
   ```
   Query: "Out of bounds array access"
   Expected: Finds "ArrayIndexOutOfRangeException" bugs
   ```

2. **Exact match only**: Query matches exact keywords
   ```
   Query: "NullReferenceException in UserController"
   Expected: Finds bugs with exact keywords
   ```

3. **Hybrid match**: Query matches both semantic and exact
   ```
   Query: "Memory leak in background service"
   Expected: Highest score to bugs matching both
   ```

4. **No match**: Query has no relevant bugs
   ```
   Query: "Flying spaghetti monster bug"
   Expected: Returns "no match" sentinel
   ```

5. **Fallback scenario**: Exact match search fails
   ```
   ADO connectivity issue
   Expected: Falls back to semantic search gracefully
   ```

---

## Monitoring & Debugging

### Logs to Watch

Enable debug logging to see hybrid search in action:

```python
# semantic_search execution
[HybridSearch] Semantic: Local index returned 10 bug(s)
[HybridSearch] Semantic: Two-pass re-score applied to 10 bug(s)

# exact_match_search execution
[HybridSearch] Exact match: WIQL returned 8 bug(s)

# merge and ranking
[HybridSearch] Merged 14 unique bugs from both approaches

# threshold filtering
[HybridSearch] No bugs met similarity threshold; returning no match
```

### Score Breakdown
Each result includes metadata with component scores:
```python
metadata = {
    "similarity_score": 0.814,      # Final hybrid score
    "exact_match_score": 0.85,      # Exact match component
    "rrf_score": 0.042,             # RRF ranking bonus
}
```

---

## Future Enhancements

1. **Learning-to-rank (LTR)**: Train model to dynamically adjust weights
2. **Query feedback**: User feedback on results tunes weights
3. **Threshold learning**: Automatically determine optimal thresholds per project
4. **Cross-lingual**: Support queries in multiple languages
5. **Temporal scoring**: Boost recent high-confidence bugs
6. **User-specific weighting**: Different weights per team/project

---

## References

- [Reciprocal Rank Fusion (RRF)](https://dl.acm.org/doi/10.1145/1571941.1572114)
- [Vector Search vs Keyword Search](https://www.elastic.co/guide/en/elasticsearch/reference/current/hybrid-search.html)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [LlamaIndex Hybrid Search](https://docs.llamaindex.ai/en/stable/examples/hybrid_search/)
