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

from pathlib import Path
import os
import re
import time


STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"

# Giải thích lựa chọn tham số trong báo cáo nhóm.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CHUNKING_METHOD = "recursive"

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 3072

COLLECTION_NAME = "rag_documents"


def embed_texts(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Embed text using the configured provider (loaded only when needed)."""
    if not texts:
        return []
    from dotenv import load_dotenv
    load_dotenv()
    provider = os.getenv("EMBEDDING_PROVIDER", "sentence_transformers").lower()
    model_name = os.getenv("EMBEDDING_MODEL", EMBEDDING_MODEL)
    if provider == "sentence_transformers":
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(model_name).encode(texts, normalize_embeddings=True).tolist()
    if provider == "openai":
        from openai import OpenAI
        response = OpenAI().embeddings.create(model=model_name, input=texts, dimensions=EMBEDDING_DIM)
        return [item.embedding for item in response.data]
    if provider == "gemini":
        from google import genai
        from google.genai import types
        client = genai.Client()
        vectors = []
        config = types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBEDDING_DIM)
        # A single request carries many texts to conserve free-tier request quota.
        for start in range(0, len(texts), 100):
            response = client.models.embed_content(
                model=model_name,
                contents=texts[start : start + 100],
                config=config,
            )
            vectors.extend(embedding.values for embedding in response.embeddings)
        return vectors
    raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {provider}")


def get_collection():
    """Mở Chroma collection dùng cosine distance."""
    import chromadb
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})


def load_documents() -> list[dict]:
    """Đọc Markdown và trả về danh sách Document."""
    documents = []
    for path in sorted(STANDARDIZED_DIR.rglob("*.md")):
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            continue
        doc_type = "legal" if "legal" in path.relative_to(STANDARDIZED_DIR).parts else "news"
        url_match = re.search(r"(?im)^(?:\*\*)?(?:url|source)(?:\*\*)?:\s*(\S+)\s*$", content)
        title_match = re.search(r"(?im)^#\s+(.+?)\s*$", content) or re.search(r"(?im)^(?:\*\*)?title(?:\*\*)?:\s*(.+?)\s*$", content)
        documents.append({"id": path.relative_to(STANDARDIZED_DIR).as_posix(), "content": content,
            "metadata": {"source": path.name, "title": title_match.group(1) if title_match else path.stem,
                         "doc_type": doc_type, "url": url_match.group(1) if url_match else None}})
    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Chia Document thành chunks có id và chunk_index."""
    chunks = []
    for document in documents:
        text = document["content"].strip()
        start = 0
        index = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            if end < len(text):
                # Prefer a natural boundary while avoiding very short chunks.
                boundary = max(text.rfind("\n\n", start, end), text.rfind("\n", start, end), text.rfind(". ", start, end))
                if boundary > start + CHUNK_SIZE // 2:
                    end = boundary + (2 if text[boundary:boundary+2] == ". " else 1)
            piece = text[start:end].strip()
            if piece:
                chunks.append({"id": f"{document['id']}::chunk-{index}", "content": piece,
                               "metadata": {**document["metadata"], "chunk_index": index}})
                index += 1
            if end >= len(text):
                break
            start = max(start + 1, end - CHUNK_OVERLAP)
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Thêm embedding vào từng chunk."""
    vectors = embed_texts([chunk["content"] for chunk in chunks], task_type="RETRIEVAL_DOCUMENT")
    if len(vectors) != len(chunks):
        raise ValueError("Embedding provider returned a different number of vectors")
    return [{**chunk, "embedding": vector} for chunk, vector in zip(chunks, vectors)]


def index_to_vectorstore(chunks: list[dict]) -> None:
    """Upsert chunks vào ChromaDB."""
    if not chunks:
        return
    collection = get_collection()
    collection.upsert(ids=[c["id"] for c in chunks], documents=[c["content"] for c in chunks],
                      embeddings=[c["embedding"] for c in chunks], metadatas=[c["metadata"] for c in chunks])


def run_pipeline() -> None:
    """Chạy load, chunk, embed và index."""
    from dotenv import load_dotenv
    load_dotenv()
    documents = load_documents()
    chunks = chunk_documents(documents)
    provider = os.getenv("EMBEDDING_PROVIDER", "sentence_transformers").lower()
    if provider == "gemini":
        collection = get_collection()
        indexed_ids = set(collection.get(include=[]).get("ids", []))
        pending = [chunk for chunk in chunks if chunk["id"] not in indexed_ids]
        if indexed_ids and pending:
            print("Resuming from saved chunks; waiting 60s for the free-tier embedding quota window.")
            time.sleep(60)
        for start in range(0, len(pending), 100):
            if start:
                print("Free-tier pacing: waiting 60s before the next 100-chunk batch.")
                time.sleep(60)
            batch = pending[start : start + 100]
            vectors = embed_texts([chunk["content"] for chunk in batch], task_type="RETRIEVAL_DOCUMENT")
            if len(vectors) != len(batch):
                raise ValueError("Embedding provider returned a different number of vectors")
            indexed = [{**chunk, "embedding": vector} for chunk, vector in zip(batch, vectors)]
            index_to_vectorstore(indexed)
            print(f"Indexed {min(start + len(batch), len(pending))}/{len(pending)} pending chunks")
        print(f"Index ready: {len(chunks)} chunks; {len(indexed_ids)} already present")
        return
    embedded_chunks = embed_chunks(chunks)
    index_to_vectorstore(embedded_chunks)
    print(f"Indexed {len(embedded_chunks)} chunks")


if __name__ == "__main__":
    run_pipeline()
