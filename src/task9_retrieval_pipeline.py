"""Task 9: hybrid retrieval with a fallback gated by original dense cosine."""

import logging
import math
import os

from .contracts import validate_search_results
from .task5_semantic_search import semantic_search
from .task6_lexical_search import lexical_search
from .task7_reranking import rerank_rrf
from .task8_pageindex_vectorless import pageindex_search


logger = logging.getLogger(__name__)
SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD", "").strip() or "0.5")
DEFAULT_TOP_K = 5


def _search_safely(search, query, top_k, method):
    try:
        results = search(query, top_k=top_k)
        validate_search_results(results, top_k=top_k, expected_method=method)
        if any(not math.isfinite(item["score"]) for item in results):
            raise ValueError("Non-finite retrieval score")
        return results
    except Exception as exc:
        # Do not log provider response bodies, credentials or document content.
        logger.warning("%s retrieval unavailable (%s)", method, type(exc).__name__)
        return []


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    use_reranking: bool = True,
) -> list[dict]:
    """Return hybrid/PageIndex results, or dense results in the ablation mode."""
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    if isinstance(top_k, bool) or not isinstance(top_k, int):
        raise TypeError("top_k must be an integer")
    if (isinstance(score_threshold, bool)
            or not isinstance(score_threshold, (int, float))
            or not math.isfinite(score_threshold) or not -1 <= score_threshold <= 1):
        raise ValueError("score_threshold must be a finite cosine value in [-1, 1]")
    if not isinstance(use_reranking, bool):
        raise TypeError("use_reranking must be a boolean")
    if not query.strip() or top_k <= 0:
        return []
    query = query.strip()
    dense = _search_safely(semantic_search, query, top_k * 2, "dense")
    if use_reranking:
        sparse = _search_safely(lexical_search, query, top_k * 2, "bm25")
        results = rerank_rrf([dense, sparse], top_k=top_k)
    else:
        results = dense[:top_k]
    # An absent dense result always permits fallback, even with a negative threshold.
    if not dense or max(item["score"] for item in dense) < score_threshold:
        fallback = _search_safely(pageindex_search, query, top_k, "pageindex")
        if fallback:
            return fallback
    validate_search_results(results, top_k=top_k)
    return results


if __name__ == "__main__":
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--threshold", type=float, default=SCORE_THRESHOLD)
    parser.add_argument("--dense-only", action="store_true")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(retrieve(args.query, args.top_k, args.threshold,
                             not args.dense_only), ensure_ascii=False, indent=2))
