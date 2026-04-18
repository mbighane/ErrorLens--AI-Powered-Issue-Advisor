"""
Local vector search service using OpenAI embeddings + numpy cosine similarity.

Embeddings and metadata are persisted as .npy / .json file pairs under
settings.vector_index_dir so the index survives application restarts without
requiring Redis Stack or any external vector database.

Index layout
------------
{vector_index_dir}/
    bugs_embeddings.npy    - float32 ndarray of shape (N, 1536)
    bugs_metadata.json     - list of N bug dicts (all scalar fields preserved)
    wiki_embeddings.npy    - float32 ndarray of shape (M, 1536)
    wiki_metadata.json     - list of M wiki-page dicts

Deduplication
-------------
Each call to index_bugs / index_wiki_pages skips items whose id / path is
already present in the persisted index so re-ingestion is safe.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from openai import OpenAI

from ..config import settings

_EMBEDDING_MODEL = "text-embedding-3-small"
_EMBEDDING_DIMS  = 1536
_MAX_TEXT_CHARS  = 4000   # well under the model's token limit

import re as _re


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode common entities before embedding."""
    text = _re.sub(r"<[^>]+>", " ", text or "")
    text = text.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"')
    return _re.sub(r"\s+", " ", text).strip()


def _truncate(text: str) -> str:
    return (text or "")[:_MAX_TEXT_CHARS]


class LocalVectorSearchService:
    """
    Drop-in replacement / complement for RedisVectorSearchService.

    Provides the same public API:
        index_bugs(bugs)          -> int   (number newly indexed)
        search_bugs(query, top_k) -> List[Dict]
        index_wiki_pages(pages)   -> int
        search_wiki_pages(query, top_k) -> List[Dict]

    Additionally exposes:
        has_bugs_indexed()  -> bool
        has_wiki_indexed()  -> bool
        enabled             -> bool  (False when OpenAI key is missing)
    """

    def __init__(self) -> None:
        self.enabled    = False
        self.init_error = ""
        self._client: Optional[OpenAI] = None

        index_dir = Path(settings.vector_index_dir)
        self._bugs_emb_path  = index_dir / "bugs_embeddings.npy"
        self._bugs_meta_path = index_dir / "bugs_metadata.json"
        self._wiki_emb_path  = index_dir / "wiki_embeddings.npy"
        self._wiki_meta_path = index_dir / "wiki_metadata.json"

        try:
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY not set — local vector search disabled")
            self._client = OpenAI(api_key=settings.openai_api_key)
            index_dir.mkdir(parents=True, exist_ok=True)
            self.enabled = True
        except Exception as exc:
            self.init_error = str(exc)

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def has_bugs_indexed(self) -> bool:
        return self._bugs_emb_path.exists() and self._bugs_meta_path.exists()

    def has_wiki_indexed(self) -> bool:
        return self._wiki_emb_path.exists() and self._wiki_meta_path.exists()

    # ------------------------------------------------------------------
    # OpenAI embedding helpers
    # ------------------------------------------------------------------

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts with a single OpenAI API call."""
        cleaned = [_truncate(t) or " " for t in texts]
        response = self._client.embeddings.create(
            input=cleaned,
            model=_EMBEDDING_MODEL,
        )
        return [item.embedding for item in response.data]

    def _embed_query(self, query: str) -> np.ndarray:
        expanded = self._expand_query(query)
        vectors = self._embed_texts([expanded])
        return np.array(vectors[0], dtype=np.float32)

    def _expand_query(self, query: str) -> str:
        """
        Use GPT to expand the query with technical synonyms and related terms
        so the embedding sits closer to root-cause level bug descriptions.
        Falls back to the original query if GPT is unavailable.
        """
        try:
            response = self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a technical search assistant. "
                            "Given a bug report query, rewrite it as a rich technical search string "
                            "by adding relevant synonyms, underlying technologies, and root-cause terms. "
                            "Keep it under 40 words. Return only the expanded text, no explanation."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                temperature=0.2,
                max_tokens=80,
            )
            expanded = response.choices[0].message.content.strip()
            print(f"[VectorSearch] Query expanded: '{query}' -> '{expanded}'")
            return expanded
        except Exception as exc:
            print(f"[VectorSearch] Query expansion failed, using original: {exc}")
            return query

    # ------------------------------------------------------------------
    # Core mechanics
    # ------------------------------------------------------------------

    @staticmethod
    def _cosine_sim(q: np.ndarray, matrix: np.ndarray) -> np.ndarray:
        qnorm = float(np.linalg.norm(q))
        if qnorm == 0:
            return np.zeros(len(matrix), dtype=np.float32)
        mnorms = np.linalg.norm(matrix, axis=1)
        mnorms[mnorms == 0] = 1e-10
        return (matrix @ q) / (mnorms * qnorm)

    def _load_index(
        self, emb_path: Path, meta_path: Path
    ) -> tuple[np.ndarray, list]:
        emb  = np.load(str(emb_path)).astype(np.float32)
        with open(meta_path, "r", encoding="utf-8") as fh:
            meta = json.load(fh)
        return emb, meta

    def _save_index(
        self,
        emb:      np.ndarray,
        meta:     list,
        emb_path: Path,
        meta_path: Path,
    ) -> None:
        np.save(str(emb_path), emb)
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=2)

    def _index_items(
        self,
        items:     List[Dict[str, Any]],
        text_fn,           # (item) -> str  — what text to embed
        id_fn,             # (item) -> str  — unique key for dedup
        emb_path:  Path,
        meta_path: Path,
    ) -> int:
        if not self.enabled or not items:
            return 0

        # Load existing index for deduplication
        existing_emb: np.ndarray = np.empty((0, _EMBEDDING_DIMS), dtype=np.float32)
        existing_meta: list      = []
        existing_ids:  set       = set()

        if emb_path.exists() and meta_path.exists():
            try:
                existing_emb, existing_meta = self._load_index(emb_path, meta_path)
                existing_ids = {id_fn(m) for m in existing_meta}
            except Exception:
                pass

        new_items = [it for it in items if id_fn(it) not in existing_ids]
        if not new_items:
            return 0

        texts   = [text_fn(it) for it in new_items]
        vectors = np.array(self._embed_texts(texts), dtype=np.float32)

        combined_emb  = np.vstack([existing_emb, vectors]) if len(existing_emb) > 0 else vectors
        combined_meta = existing_meta + new_items

        self._save_index(combined_emb, combined_meta, emb_path, meta_path)
        return len(new_items)

    def _search_items(
        self,
        query:     str,
        emb_path:  Path,
        meta_path: Path,
        top_k:     int,
    ) -> List[Dict[str, Any]]:
        if not self.enabled or not emb_path.exists() or not meta_path.exists():
            return []

        embeddings, metadata = self._load_index(emb_path, meta_path)
        q_vec  = self._embed_query(query)
        scores = self._cosine_sim(q_vec, embeddings)

        top_indices = np.argsort(scores)[::-1][:top_k]
        results: List[Dict[str, Any]] = []
        for idx in top_indices:
            score = float(scores[idx])
            if score > 0:
                results.append({**metadata[idx], "similarity_score": score})
        return results

    # ------------------------------------------------------------------
    # Bug index API  (mirrors RedisVectorSearchService)
    # ------------------------------------------------------------------

    def index_bugs(self, bugs: List[Dict[str, Any]]) -> int:
        """
        Embed and persist a list of bug dicts.
        Each bug dict must have at least: id, title.
        Optional rich fields: description, root_cause_analysis, suggested_fix.
        Returns the number of newly indexed items (0 if all duplicates).
        """
        def text_of(bug: Dict) -> str:
            rca = _strip_html(bug.get('root_cause_analysis', ''))
            fix = _strip_html(bug.get('suggested_fix', ''))
            analysis = " ".join(filter(None, [rca, fix]))
            parts = [
                f"Title: {_strip_html(bug.get('title', ''))}",
                f"Description: {_strip_html(bug.get('description', ''))}",
                f"Analysis: {analysis}",
            ]
            return "\n".join(p for p in parts if p.split(": ", 1)[-1].strip())

        return self._index_items(
            bugs,
            text_fn=text_of,
            id_fn=lambda b: str(b.get("id", "")),
            emb_path=self._bugs_emb_path,
            meta_path=self._bugs_meta_path,
        )

    def search_bugs(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search the local bug embedding index for the closest matches."""
        return self._search_items(
            query,
            self._bugs_emb_path,
            self._bugs_meta_path,
            top_k,
        )

    def score_bugs_in_memory(self, query: str, bugs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Compute semantic similarity scores for a list of bug dicts in-memory using
        OpenAI embeddings. Does NOT require a pre-built index on disk.
        Returns the same bugs sorted by descending semantic score, with
        'similarity_score' set to the cosine similarity value.
        """
        if not self.enabled or not bugs:
            return bugs

        def text_of(bug: Dict) -> str:
            rca = _strip_html(bug.get('root_cause_analysis', ''))
            fix = _strip_html(bug.get('suggested_fix', ''))
            analysis = " ".join(filter(None, [rca, fix]))
            parts = [
                f"Title: {_strip_html(bug.get('title', ''))}",
                f"Description: {_strip_html(bug.get('description', ''))}",
                f"Analysis: {analysis}",
            ]
            return "\n".join(p for p in parts if p.split(": ", 1)[-1].strip())

        try:
            expanded_query = self._expand_query(query)
            bug_texts = [text_of(b) for b in bugs]
            all_texts = [expanded_query] + bug_texts
            all_vectors = np.array(self._embed_texts(all_texts), dtype=np.float32)
            q_vec = all_vectors[0]
            bug_matrix = all_vectors[1:]
            scores = self._cosine_sim(q_vec, bug_matrix)
            scored = [
                {**bug, "similarity_score": float(scores[i])}
                for i, bug in enumerate(bugs)
            ]
            scored.sort(key=lambda x: x["similarity_score"], reverse=True)
            return scored
        except Exception as exc:
            print(f"[LocalVectorSearch] score_bugs_in_memory failed: {exc}")
            return bugs

    def rescore_bugs_from_search_results(
        self,
        query: str,
        bugs: List[Dict[str, Any]],
        top_n_for_context: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Two-pass semantic rescoring that uses the content of the initial search
        results to enrich the query before the final scoring pass.

        Pass 1 — initial semantic score
        --------------------------------
        Embed the GPT-expanded query against all bug texts
        (title + description + combined RCA/suggested-fix).
        Pick the top `top_n_for_context` bugs — these are the closest semantic
        neighbours in the existing index, even if their raw scores are low.

        Pass 2 — feedback-enriched rescore
        ------------------------------------
        Extract the actual text content of those top bugs and append it to the
        expanded query as "context from similar bugs".  Re-embed this richer
        query and score ALL bugs again.  The enriched query vector sits much
        closer to root-cause vocabulary used in the rest of the index, lifting
        scores for bugs that share that vocabulary.

        Returns all bugs sorted by their Pass-2 similarity_score (descending).
        Falls back to plain score_bugs_in_memory on any error.
        """
        if not self.enabled or not bugs:
            return bugs

        def text_of(bug: Dict) -> str:
            rca = _strip_html(bug.get("root_cause_analysis", ""))
            fix = _strip_html(bug.get("suggested_fix", ""))
            analysis = " ".join(filter(None, [rca, fix]))
            parts = [
                f"Title: {_strip_html(bug.get('title', ''))}",
                f"Description: {_strip_html(bug.get('description', ''))}",
                f"Analysis: {analysis}",
            ]
            return "\n".join(p for p in parts if p.split(": ", 1)[-1].strip())

        try:
            # ── PASS 1: initial scoring with expanded query ──────────────
            expanded_query = self._expand_query(query)
            bug_texts = [text_of(b) for b in bugs]

            pass1_texts   = [expanded_query] + bug_texts
            pass1_vectors = np.array(self._embed_texts(pass1_texts), dtype=np.float32)
            q1_vec        = pass1_vectors[0]
            bug_matrix    = pass1_vectors[1:]
            pass1_scores  = self._cosine_sim(q1_vec, bug_matrix)

            # Rank bugs by pass-1 score, pick the top N for context
            ranked_indices = np.argsort(pass1_scores)[::-1][:top_n_for_context]
            top_bugs       = [bugs[i] for i in ranked_indices]

            print(f"[VectorSearch] Pass-1 top-{len(top_bugs)} bugs used for context:")
            for i in ranked_indices:
                print(f"  pass1={pass1_scores[i]:.4f} | {bugs[i].get('title', '')}")

            # ── BUILD ENRICHED QUERY ─────────────────────────────────────
            context_lines: List[str] = []
            for tb in top_bugs:
                snippet = text_of(tb)[:300]
                if snippet.strip():
                    context_lines.append(snippet)

            context_block = " | ".join(context_lines)
            enriched_query = _truncate(
                f"{expanded_query}. Context from similar bugs: {context_block}"
            )
            print(f"[VectorSearch] Enriched query (first 200 chars):\n  {enriched_query[:200]}...")

            # ── PASS 2: rescore ALL bugs with enriched query ─────────────
            pass2_texts   = [enriched_query] + bug_texts   # reuse bug_texts from pass 1
            pass2_vectors = np.array(self._embed_texts(pass2_texts), dtype=np.float32)
            q2_vec        = pass2_vectors[0]
            bug_matrix2   = pass2_vectors[1:]
            pass2_scores  = self._cosine_sim(q2_vec, bug_matrix2)

            scored = [
                {
                    **bug,
                    "similarity_score":       float(pass2_scores[i]),
                    "similarity_score_pass1": float(pass1_scores[i]),
                }
                for i, bug in enumerate(bugs)
            ]
            scored.sort(key=lambda x: x["similarity_score"], reverse=True)

            print(f"[VectorSearch] Pass-2 final scores:")
            for r in scored:
                delta  = r["similarity_score"] - r["similarity_score_pass1"]
                marker = " <<< ABOVE 0.50" if r["similarity_score"] >= 0.50 else ""
                print(
                    f"  pass1={r['similarity_score_pass1']:.4f}  "
                    f"pass2={r['similarity_score']:.4f}  "
                    f"delta={delta:+.4f}{marker}  | {r.get('title', '')}"
                )
            return scored

        except Exception as exc:
            print(f"[LocalVectorSearch] rescore_bugs_from_search_results failed: {exc}")
            return self.score_bugs_in_memory(query, bugs)

    # ------------------------------------------------------------------
    # Wiki index API  (mirrors RedisVectorSearchService)
    # ------------------------------------------------------------------

    def index_wiki_pages(self, pages: List[Dict[str, Any]]) -> int:
        """
        Embed and persist a list of wiki page dicts.
        Each page dict must have at least: title.
        Optional rich fields: path, content.
        Returns the number of newly indexed items (0 if all duplicates).
        """
        def text_of(page: Dict) -> str:
            parts = [
                f"Title: {page.get('title', '')}",
                f"Path: {page.get('path', '')}",
                f"Content: {(page.get('content', '') or '')[:2000]}",
            ]
            return "\n".join(p for p in parts if p.split(": ", 1)[-1].strip())

        def page_id(page: Dict) -> str:
            return str(page.get("id") or page.get("path") or page.get("title", ""))

        return self._index_items(
            pages,
            text_fn=text_of,
            id_fn=page_id,
            emb_path=self._wiki_emb_path,
            meta_path=self._wiki_meta_path,
        )

    def search_wiki_pages(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search the local wiki embedding index for the closest matches."""
        return self._search_items(
            query,
            self._wiki_emb_path,
            self._wiki_meta_path,
            top_k,
        )
