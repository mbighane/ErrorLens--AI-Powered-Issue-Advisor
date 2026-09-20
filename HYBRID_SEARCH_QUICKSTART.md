# Hybrid Search Quick Start Guide

## What Changed?

ErrorLens now performs **Hybrid Search** instead of sequential fallback search:

### Before (Sequential/Waterfall)
```
Query → Semantic Search → No results? → Exact Match Search → No results? → Return "no match"
```
❌ Only uses exact match if semantic fails (slow, limited coverage)

### After (Hybrid/Parallel)
```
Query → [Semantic Search] ─┐
        [Exact Match ─────→ [Merge & Rank] → Return Top Results
        Search]     ─┘
```
✅ Both searches run in parallel, results intelligently merged

---

## Key Differences

### Performance
- **Old**: ~500-2000ms (sequential, one search runs after another)
- **New**: ~500-2000ms (parallel, both run simultaneously)
- **Result**: Faster response time, better results

### Coverage
- **Old**: Either semantic OR exact match results
- **New**: BOTH semantic AND exact match results combined
- **Result**: More comprehensive bug discovery

### Scoring
- **Old**: Single similarity score (0.0-1.0)
- **New**: Hybrid score (semantic 60% + exact match 40%)
- **Result**: Balanced, more relevant results

---

## Usage (No Code Changes Required!)

The hybrid search is **automatic** and **transparent**:

```python
# Your existing code works unchanged
service = ADOBugSearchService()
bugs = await service.search_similar_bugs("NullReferenceException in controller")

# Returns: BugResult list or "no match" sentinel
# Now using hybrid search under the hood!
```

---

## Understanding Results

### Score Breakdown

Each bug result now includes enhanced metadata:

```python
BugResult(
    id="123",
    title="NullReferenceException in UserController",
    description="...",
    similarity_score=0.814,  # ← Hybrid score
    metadata={
        "exact_match_score": 0.85,    # Exact match component
        "rrf_score": 0.042,           # Ranking bonus
        "work_item_type": "Issue",
    }
)
```

### Interpreting Scores

| Hybrid Score | Meaning | Confidence |
|---|---|---|
| 0.9 - 1.0 | Excellent match | Very High |
| 0.8 - 0.9 | Very good match | High |
| 0.7 - 0.8 | Good match | Medium-High |
| 0.6 - 0.7 | Fair match | Medium |
| < 0.6 | Weak match | Low |

### Score Sources

**Hybrid Score = 0.6 × semantic_score + 0.4 × exact_match_score**

- **Semantic Score**: From vector embedding similarity
  - Captures conceptual similarity
  - Robust to phrasing variations
  
- **Exact Match Score**: From keyword overlap
  - Title exact match: 1.0
  - Title token overlap: 0.3-0.7
  - Description keyword match: 0.2-0.5

---

## Configuration & Tuning

### Default Weights (Balanced)
```python
SEMANTIC_WEIGHT = 0.6        # 60% - Trust embeddings
EXACT_MATCH_WEIGHT = 0.4     # 40% - Ensure keywords match
```

### Customization Examples

**For high precision (fewer false positives)**:
```python
# Edit backend/app/services/hybrid_bug_search_service.py
SEMANTIC_WEIGHT = 0.7        # Favor embeddings
EXACT_MATCH_WEIGHT = 0.3
```

**For high recall (find all potential matches)**:
```python
SEMANTIC_WEIGHT = 0.5        # Equal weight
EXACT_MATCH_WEIGHT = 0.5
```

**For keyword-focused (exact match priority)**:
```python
SEMANTIC_WEIGHT = 0.3        # Less trust in embeddings
EXACT_MATCH_WEIGHT = 0.7     # Prioritize exact keywords
```

---

## Monitoring & Logs

### Expected Log Output

```
[HybridSearch] Semantic: Local index returned 8 bug(s)
[HybridSearch] Semantic: Two-pass re-score applied to 8 bug(s)
[HybridSearch] Exact match: WIQL returned 7 bug(s)
[HybridSearch] Merged 12 unique bugs from both approaches
[ADOBugSearchService] Hybrid search returned 5 result(s)
```

### Debug Info in Results

Metadata includes detailed scoring information:
- `similarity_score`: Final hybrid score
- `exact_match_score`: Exact match component
- `rrf_score`: Ranking bonus from RRF

---

## Fallback Behavior

If hybrid search fails:

```
Hybrid Search fails
    ↓
Fallback to Semantic Search only
    ↓
Still fails?
    ↓
Return "no match" sentinel
```

No queries are lost—the system gracefully degrades.

---

## Examples

### Example 1: Semantic + Exact Match
**Query**: "Memory leak in list"

```
Results:
1. "ArrayList not releasing memory" (0.814)
   - Semantic: 0.79 (embeddings found conceptual match)
   - Exact: 0.85 (keywords "memory" + "list" match)
   - Rank: #1 because both methods found it

2. "Out of memory exception" (0.642)
   - Semantic: 0.87 (embeddings strong match)
   - Exact: 0.30 (no exact keywords)
   - Rank: #2 because semantic was strong
```

### Example 2: Exact Match Only
**Query**: "NullReferenceException in UserController"

```
Results:
1. "UserController.GetUser throws NullReferenceException" (0.891)
   - Semantic: 0.60 (moderate embedding match)
   - Exact: 0.98 (nearly exact keywords)
   - Rank: #1 because exact match is very high
```

### Example 3: Semantic Only
**Query**: "Widget rendering issue"

```
Results:
1. "UI component not displaying correctly" (0.745)
   - Semantic: 0.87 (embeddings understand semantics)
   - Exact: 0.50 (partial keyword overlap)
   - Rank: #1 because semantic understanding is strong
```

---

## FAQ

**Q: Do I need to change my code?**
A: No! Hybrid search is automatic and transparent.

**Q: Will it be slower?**
A: No. Both searches run in parallel, so overall time is roughly the same.

**Q: Can I go back to semantic-only search?**
A: Yes, modify weights:
```python
SEMANTIC_WEIGHT = 1.0
EXACT_MATCH_WEIGHT = 0.0
```

**Q: What if my queries are very different from bug titles?**
A: That's exactly when hybrid search shines. Semantic search will find conceptually similar bugs even with different wording.

**Q: What if I have many exact keyword matches?**
A: Hybrid search will boost those results while still considering semantic similarity.

---

## Performance Tips

1. **Pre-warm the vector index**: Index bugs on startup (already done)
2. **Use specific queries**: "NullReferenceException in UserController" > "error"
3. **Monitor similarity threshold**: Default is 0.6 (`search_similarity_threshold` in config)
4. **Tune weights for your domain**: Different teams may prefer different ratios

---

## Troubleshooting

### No results returned
- Check logs for `[HybridSearch]` messages
- Verify Azure DevOps connection
- Try simpler query (fewer keywords)
- Lower similarity threshold if appropriate

### Low confidence scores
- Query may not match existing bugs well
- Try more specific keywords
- Check if bugs are indexed (vector index age)

### One method consistently outperforms
- Adjust weights accordingly
- Semantic heavy if embeddings work well: 0.7/0.3
- Keyword heavy if exact matches work better: 0.3/0.7

---

## Next Steps

1. **Review** the [Hybrid Search Guide](HYBRID_SEARCH_GUIDE.md) for technical details
2. **Monitor** logs to see hybrid search in action
3. **Tune** weights based on your usage patterns
4. **Feedback**: Report results quality improvements!
