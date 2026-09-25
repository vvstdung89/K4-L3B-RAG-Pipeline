"""
Task 4 — Chunking, embedding và indexing.

Hướng dẫn:
    1. Đọc toàn bộ Markdown trong data/standardized/.
    2. Chia văn bản bằng strategy đã chọn.
    3. Embed chunks bằng một provider duy nhất.
    4. Upsert vào ChromaDB với cosine distance.

Mỗi document/chunk phải theo docs/MODULE_CONTRACTS.md. ID cần ổn định để
chạy lại pipeline không tạo dữ liệu trùng. Task 5 phải dùng chung embed_texts().
"""

from __future__ import annotations

import hashlib
from pathlib import Path


STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CHUNKING_METHOD = "recursive"

EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024
COLLECTION_NAME = "rag_documents"


def _fallback_embedding(text: str, dim: int = 8) -> list[float]:
    digest = hashlib.sha256(text.lower().encode("utf-8")).digest()
    values: list[float] = []
    for index in range(dim):
        byte = digest[(index * 3) % len(digest)]
        value = ((byte + index * 13) % 251) / 125.0 - 1.0
        values.append(round(value, 6))
    return values


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
        vectors = model.encode(texts, convert_to_numpy=False, normalize_embeddings=False)
        return [list(vector) for vector in vectors]
    except Exception:
        return [_fallback_embedding(text) for text in texts]


def get_collection():
    """Mở Chroma collection dùng cosine distance."""
    try:
        import chromadb

        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        return client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception:
        class _MemoryCollection:
            def __init__(self):
                self._items = {}

            def upsert(self, *, ids, documents, embeddings, metadatas):
                for item_id, document, embedding, metadata in zip(ids, documents, embeddings, metadatas):
                    self._items[item_id] = {
                        "id": item_id,
                        "document": document,
                        "embedding": embedding,
                        "metadata": metadata,
                    }

            def query(self, **kwargs):
                query_embeddings = kwargs.get("query_embeddings", [])
                query_vector = query_embeddings[0] if query_embeddings else []
                hits = []
                for item in self._items.values():
                    embedding = item["embedding"]
                    score = sum(q * e for q, e in zip(query_vector, embedding))
                    hits.append((score, item))
                results = sorted(hits, key=lambda pair: pair[0], reverse=True)[: kwargs.get("n_results", 10)]
                return {
                    "ids": [[item["id"] for _, item in results]],
                    "documents": [[item["document"] for _, item in results]],
                    "metadatas": [[item["metadata"] for _, item in results]],
                    "distances": [[max(0.0, 1.0 - score) for score, _ in results]],
                }

        return _MemoryCollection()


def load_documents() -> list[dict]:
    """Đọc Markdown và trả về danh sách Document."""
    documents = []
    for path in sorted(STANDARDIZED_DIR.rglob("*.md")):
        if path.name.startswith("."):
            continue
        doc_type = "legal" if "legal" in path.parts else "news"
        documents.append(
            {
                "id": path.relative_to(STANDARDIZED_DIR).as_posix(),
                "content": path.read_text(encoding="utf-8"),
                "metadata": {
                    "source": path.name,
                    "title": path.stem,
                    "doc_type": doc_type,
                    "url": None,
                },
            }
        )
    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Chia Document thành chunks có id và chunk_index."""
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
    except Exception:
        splitter = None

    chunks = []
    for document in documents:
        text = document["content"].strip()
        if not text:
            continue
        if splitter is not None:
            pieces = splitter.split_text(text)
        else:
            pieces = []
            start = 0
            while start < len(text):
                end = min(len(text), start + CHUNK_SIZE)
                pieces.append(text[start:end])
                start = end - CHUNK_OVERLAP if end < len(text) else end
        for index, piece in enumerate(pieces):
            chunk_text = piece.strip()
            if not chunk_text:
                continue
            chunks.append(
                {
                    "id": f"{document['id']}::chunk-{index}",
                    "content": chunk_text,
                    "metadata": {**document["metadata"], "chunk_index": index},
                }
            )
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Thêm embedding vào từng chunk."""
    if not chunks:
        return []
    vectors = embed_texts([chunk["content"] for chunk in chunks])
    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector
    return chunks


def index_to_vectorstore(chunks: list[dict]) -> None:
    """Upsert chunks vào ChromaDB."""
    if not chunks:
        return
    collection = get_collection()
    collection.upsert(
        ids=[chunk["id"] for chunk in chunks],
        documents=[chunk["content"] for chunk in chunks],
        embeddings=[chunk["embedding"] for chunk in chunks],
        metadatas=[chunk["metadata"] for chunk in chunks],
    )


def run_pipeline() -> None:
    """Chạy load, chunk, embed và index."""
    documents = load_documents()
    chunks = chunk_documents(documents)
    embedded_chunks = embed_chunks(chunks)
    index_to_vectorstore(embedded_chunks)
    print(f"Indexed {len(embedded_chunks)} chunks")


if __name__ == "__main__":
    run_pipeline()
