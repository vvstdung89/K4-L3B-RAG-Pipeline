"""Task 7: Reciprocal Rank Fusion, independent of raw score scales."""

from copy import deepcopy

from .contracts import validate_document, validate_search_results


def rerank_rrf(
    ranked_lists: list[list[dict]], top_k: int = 5, k: int = 60,
) -> list[dict]:
    """Fuse by ID using sum(1 / (k + rank)); ranks start at one."""
    if isinstance(top_k, bool) or not isinstance(top_k, int):
        raise TypeError("top_k must be an integer")
    if isinstance(k, bool) or not isinstance(k, int) or k < 0:
        raise ValueError("k must be a non-negative integer")
    if top_k <= 0:
        return []
    scores, items = {}, {}
    for ranking in ranked_lists:
        seen = set()
        for item in ranking:
            validate_document(item, require_chunk=True)
            item_id = item["id"]
            if item_id in seen:
                continue
            seen.add(item_id)
            scores[item_id] = scores.get(item_id, 0.0) + 1 / (k + len(seen))
            items.setdefault(item_id, item)
    results = []
    for item_id in sorted(scores, key=lambda key: (-scores[key], key))[:top_k]:
        item = deepcopy(items[item_id])
        item.update(score=scores[item_id], retrieval_method="hybrid")
        results.append(item)
    validate_search_results(results, top_k=top_k, expected_method="hybrid")
    return results


if __name__ == "__main__":
    import json
    from .task5_semantic_search import semantic_search
    from .task6_lexical_search import lexical_search

    query = "du lịch Việt Nam"
    print(json.dumps(rerank_rrf([semantic_search(query), lexical_search(query)]),
                     ensure_ascii=True, indent=2))
