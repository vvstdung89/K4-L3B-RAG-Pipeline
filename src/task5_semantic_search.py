"""
Task 5 — Semantic search.

Embed query bằng chính hàm của Task 4, query ChromaDB và đổi cosine distance
thành similarity. Output phải theo SearchResult, sort giảm dần và không quá top_k.
"""

from .task4_chunking_indexing import embed_texts, get_collection


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """Trả về dense SearchResult theo score giảm dần."""
    if top_k <= 0 or not query.strip():
        return []
    try:
        query_vector = embed_texts([query], task_type="RETRIEVAL_QUERY")[0]
    except TypeError as exc:
        # Keep compatibility with lightweight tests or external providers that
        # still expose the original one-argument embed_texts function.
        if "task_type" not in str(exc):
            raise
        query_vector = embed_texts([query])[0]
    response = get_collection().query(query_embeddings=[query_vector], n_results=top_k,
                                      include=["documents", "metadatas", "distances"])
    ids = response.get("ids", [[]])[0]
    documents = response.get("documents", [[]])[0]
    metadatas = response.get("metadatas", [[]])[0]
    distances = response.get("distances", [[]])[0]
    results = []
    for item_id, content, metadata, distance in zip(ids, documents, metadatas, distances):
        results.append({"id": item_id, "content": content, "score": float(1.0 - distance),
                        "metadata": metadata, "retrieval_method": "dense"})
    return sorted(results, key=lambda item: item["score"], reverse=True)[:top_k]


if __name__ == "__main__":
    for result in semantic_search("test query", top_k=3):
        print(result)
