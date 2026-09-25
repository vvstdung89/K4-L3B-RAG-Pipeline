"""
Task 5 — Semantic search.

Embed query bằng chính hàm của Task 4, query ChromaDB và đổi cosine distance
thành similarity. Output phải theo SearchResult, sort giảm dần và không quá top_k.
"""

from .contracts import validate_search_results
from .task4_chunking_indexing import embed_texts, get_collection


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """Trả về dense SearchResult theo score giảm dần."""
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    if not isinstance(top_k, int) or isinstance(top_k, bool):
        raise TypeError("top_k must be an integer")
    query = query.strip()
    if not query or top_k <= 0:
        return []

    collection = get_collection()
    count = collection.count()
    if not count:
        return []
    query_vector = embed_texts([query])[0]
    response = collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k, count),
        include=["documents", "metadatas", "distances"],
    )
    results = []
    for item_id, content, metadata, distance in zip(
        response["ids"][0],
        response["documents"][0],
        response["metadatas"][0],
        response["distances"][0],
    ):
        metadata = dict(metadata)
        # Task 4 stores missing URLs as empty strings for Chroma compatibility.
        metadata["url"] = metadata.get("url") or None
        results.append({
            "id": item_id,
            "content": content,
            # Keep the original cosine scale, including negative similarities.
            "score": float(1.0 - distance),
            "metadata": metadata,
            "retrieval_method": "dense",
        })
    results.sort(key=lambda item: (-item["score"], item["id"]))
    results = results[:top_k]
    validate_search_results(results, top_k=top_k, expected_method="dense")
    return results


if __name__ == "__main__":
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Semantic search over the Task 4 index")
    parser.add_argument("query", nargs="?", default="du lịch Việt Nam")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(semantic_search(args.query, args.top_k), ensure_ascii=False, indent=2))
