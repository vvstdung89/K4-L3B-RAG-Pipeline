"""
Task 5 — Semantic search.

Embed query bằng chính hàm của Task 4, query ChromaDB và đổi cosine distance
thành similarity. Output phải theo SearchResult, sort giảm dần và không quá top_k.
"""

from .task4_chunking_indexing import embed_texts, get_collection


def restore_metadata(metadata: dict) -> dict:
    """Chroma lưu url=None thành chuỗi rỗng; trả lại đúng contract."""
    restored = dict(metadata)
    restored["url"] = restored.get("url") or None
    return restored


def search_by_vector(query_vector: list[float], top_k: int = 10) -> list[dict]:
    """Dense search từ một vector có sẵn (dùng cho HyDE và tìm chunk lân cận)."""
    response = get_collection().query(
        query_embeddings=[query_vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    results = []
    for item_id, content, metadata, distance in zip(
        response["ids"][0],
        response["documents"][0],
        response["metadatas"][0],
        response["distances"][0],
    ):
        results.append({
            "id": item_id,
            "content": content,
            "score": max(0.0, 1.0 - float(distance)),
            "metadata": restore_metadata(metadata),
            "retrieval_method": "dense",
        })
    return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """Trả về dense SearchResult theo score giảm dần."""
    query_vector = embed_texts([query])[0]
    return search_by_vector(query_vector, top_k)


if __name__ == "__main__":
    for result in semantic_search("Quyền của khách du lịch", top_k=3):
        print(round(result["score"], 3), result["id"])
