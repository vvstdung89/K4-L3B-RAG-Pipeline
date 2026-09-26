"""
Task 6 — Lexical search bằng BM25.

Dùng cùng corpus chunks với Task 5. BM25 phù hợp với từ khóa chính xác, mã tài
liệu và tên riêng. Output phải theo SearchResult và sort score giảm dần.
"""

import re
import unicodedata


CORPUS: list[dict] = []

_index_cache: dict = {"key": None, "bm25": None}


def tokenize(text: str) -> list[str]:
    """Tách từ theo âm tiết; chuẩn hóa NFC để 'Điều' viết NFC/NFD khớp nhau."""
    text = unicodedata.normalize("NFC", text).lower()
    return re.findall(r"\w+", text)


def load_corpus() -> list[dict]:
    """Nạp chunks từ ChromaDB để BM25 dùng đúng corpus của dense search."""
    from .task4_chunking_indexing import get_collection
    from .task5_semantic_search import restore_metadata

    data = get_collection().get(include=["documents", "metadatas"])
    return [
        {"id": item_id, "content": content, "metadata": restore_metadata(metadata)}
        for item_id, content, metadata in zip(data["ids"], data["documents"], data["metadatas"])
    ]


def reload_corpus() -> None:
    """Gọi sau khi index lại để BM25 thấy chunk mới."""
    CORPUS[:] = load_corpus()
    _index_cache["key"] = None


def build_bm25_index(corpus: list[dict]):
    """Tạo BM25 index từ cùng corpus chunks của Task 4."""
    from rank_bm25 import BM25Okapi

    return BM25Okapi([tokenize(item["content"]) for item in corpus])


def _get_index(corpus: list[dict]):
    key = (id(corpus), len(corpus), corpus[0]["id"] if corpus else None)
    if _index_cache["key"] != key:
        _index_cache["bm25"] = build_bm25_index(corpus)
        _index_cache["tokens"] = [set(tokenize(item["content"])) for item in corpus]
        _index_cache["key"] = key
    return _index_cache["bm25"], _index_cache["tokens"]


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """Trả về BM25 SearchResult theo score giảm dần."""
    if not CORPUS:
        CORPUS.extend(load_corpus())
    query_tokens = tokenize(query)
    if not CORPUS or top_k <= 0 or not query_tokens:
        return []
    bm25, token_sets = _get_index(CORPUS)
    scores = bm25.get_scores(query_tokens)
    # Chỉ giữ chunk chứa ít nhất một từ của query. Không lọc theo score > 0 vì
    # với corpus nhỏ IDF có thể bằng 0 dù chunk vẫn khớp từ khóa.
    matching = [index for index, tokens in enumerate(token_sets) if tokens.intersection(query_tokens)]
    ranked = sorted(matching, key=lambda index: scores[index], reverse=True)
    results = []
    for index in ranked[:top_k]:
        item = CORPUS[index]
        results.append({
            "id": item["id"],
            "content": item["content"],
            "score": float(scores[index]),
            "metadata": item["metadata"],
            "retrieval_method": "bm25",
        })
    return results


if __name__ == "__main__":
    for result in lexical_search("thẻ hướng dẫn viên du lịch quốc tế", top_k=3):
        print(round(result["score"], 3), result["id"])
