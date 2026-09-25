"""
Task 6 — Lexical search bằng BM25.

Dùng cùng corpus chunks với Task 5. BM25 phù hợp với từ khóa chính xác, mã tài
liệu và tên riêng. Output phải theo SearchResult và sort score giảm dần.
"""


CORPUS: list[dict] = []


def build_bm25_index(corpus: list[dict]):
    """Tạo BM25 index từ cùng corpus chunks của Task 4."""
    try:
        from rank_bm25 import BM25Okapi

        tokenized = [item["content"].lower().split() for item in corpus]
        return BM25Okapi(tokenized)
    except Exception:
        class _FallbackBM25:
            def __init__(self, source):
                self.source = source

            def get_scores(self, query_tokens):
                scores = []
                for item in self.source:
                    text = item["content"].lower().split()
                    token_counts = {}
                    for token in text:
                        token_counts[token] = token_counts.get(token, 0) + 1
                    total = 0.0
                    for token in query_tokens:
                        total += float(token_counts.get(token, 0))
                    scores.append(total)
                return scores

        return _FallbackBM25(corpus)


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """Trả về BM25 SearchResult theo score giảm dần."""
    if not CORPUS or not query or top_k <= 0:
        return []

    bm25 = build_bm25_index(CORPUS)
    scores = bm25.get_scores(query.lower().split())
    ranked_indices = sorted(range(len(scores)), key=lambda idx: scores[idx], reverse=True)
    results = []
    for index in ranked_indices[:top_k]:
        if not 0 <= index < len(CORPUS):
            continue
        if scores[index] <= 0:
            continue
        item = CORPUS[index]
        results.append(
            {
                "id": item["id"],
                "content": item["content"],
                "score": float(scores[index]),
                "metadata": item["metadata"],
                "retrieval_method": "bm25",
            }
        )
    return results


if __name__ == "__main__":
    for result in lexical_search("test query", top_k=3):
        print(result)
