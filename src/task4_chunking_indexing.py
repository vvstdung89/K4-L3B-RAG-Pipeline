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

import os
import re
import unicodedata
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

STANDARDIZED_DIR = PROJECT_ROOT / "data" / "standardized"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"

# 500 ký tự ~ 1 khoản luật hoặc 1 đoạn bài viết; overlap 50 giữ câu nối giữa 2 chunk.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CHUNKING_METHOD = "recursive"

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai").strip().lower()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large").strip()
EMBEDDING_DIMS = {
    "text-embedding-3-large": 3072,
    "text-embedding-3-small": 1536,
    "BAAI/bge-m3": 1024,
}
EMBEDDING_DIM = EMBEDDING_DIMS.get(EMBEDDING_MODEL, 0)
EMBED_BATCH_SIZE = 96

COLLECTION_NAME = "rag_documents"

_collection = None


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed bằng provider trong .env; Task 4 (chunk) và Task 5 (query) dùng chung."""
    if not texts:
        return []
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = [text.replace("\n", " ") for text in texts[start:start + EMBED_BATCH_SIZE]]
        vectors.extend(_embed_batch(batch))
    return vectors


def _embed_batch(batch: list[str]) -> list[list[float]]:
    if EMBEDDING_PROVIDER == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=60, max_retries=3)
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        return [item.embedding for item in response.data]
    if EMBEDDING_PROVIDER == "gemini":
        from google import genai

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.embed_content(model=EMBEDDING_MODEL, contents=batch)
        return [list(item.values) for item in response.embeddings]
    if EMBEDDING_PROVIDER == "sentence_transformers":
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(EMBEDDING_MODEL)
        return model.encode(batch, normalize_embeddings=True).tolist()
    raise ValueError(f"EMBEDDING_PROVIDER không hỗ trợ: {EMBEDDING_PROVIDER}")


def get_collection():
    """Mở Chroma collection dùng cosine distance."""
    global _collection
    if _collection is None:
        import chromadb

        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine", "embedding_model": EMBEDDING_MODEL},
        )
    return _collection


def _parse_markdown(path: Path) -> tuple[str, str | None, str]:
    """Tách title/url từ header Task 3 (nếu có) và trả về nội dung chính."""
    text = unicodedata.normalize("NFC", path.read_text(encoding="utf-8"))
    title = unicodedata.normalize("NFC", path.stem)
    url = None
    heading = re.match(r"^#\s+(.+)$", text, re.MULTILINE)
    source = re.search(r"^\*\*Source:\*\*\s*(\S+)", text, re.MULTILINE)
    if source:
        url = source.group(1) if source.group(1).startswith("http") else None
    if heading and source:
        title = heading.group(1).strip()
        # Bỏ header metadata; nội dung bắt đầu sau dòng '---' đầu tiên.
        parts = re.split(r"^---\s*$", text, maxsplit=1, flags=re.MULTILINE)
        if len(parts) == 2:
            text = parts[1]
    return title, url, text.strip()


def load_documents() -> list[dict]:
    """Đọc Markdown và trả về danh sách Document."""
    documents = []
    for path in sorted(STANDARDIZED_DIR.rglob("*.md")):
        relative = path.relative_to(STANDARDIZED_DIR)
        title, url, content = _parse_markdown(path)
        if not content:
            continue
        doc_type = "legal" if relative.parts[0] == "legal" else "news"
        documents.append({
            "id": unicodedata.normalize("NFC", relative.as_posix()),
            "content": content,
            "metadata": {
                "source": unicodedata.normalize("NFC", path.name),
                "title": title,
                "doc_type": doc_type,
                "url": url,
            },
        })
    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Chia Document thành chunks có id và chunk_index."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", "; ", ", ", " ", ""],
    )
    chunks = []
    for document in documents:
        pieces = [piece.strip() for piece in splitter.split_text(document["content"])]
        for index, text in enumerate(piece for piece in pieces if piece):
            chunks.append({
                "id": f"{document['id']}::chunk-{index}",
                "content": text,
                "metadata": {**document["metadata"], "chunk_index": index},
            })
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Thêm embedding vào từng chunk (không sửa list gốc)."""
    vectors = embed_texts([chunk["content"] for chunk in chunks])
    return [{**chunk, "embedding": vector} for chunk, vector in zip(chunks, vectors)]


def _chroma_metadata(metadata: dict) -> dict:
    # Chroma không nhận None; url rỗng được đổi lại thành None khi đọc ra.
    return {key: ("" if value is None else value) for key, value in metadata.items()}


def index_to_vectorstore(chunks: list[dict]) -> None:
    """Upsert chunks vào ChromaDB và xóa chunk cũ không còn trong corpus."""
    collection = get_collection()
    new_ids = {chunk["id"] for chunk in chunks}
    stale = [item for item in collection.get(include=[])["ids"] if item not in new_ids]
    if stale:
        collection.delete(ids=stale)
    for start in range(0, len(chunks), 500):
        batch = chunks[start:start + 500]
        collection.upsert(
            ids=[chunk["id"] for chunk in batch],
            documents=[chunk["content"] for chunk in batch],
            embeddings=[chunk["embedding"] for chunk in batch],
            metadatas=[_chroma_metadata(chunk["metadata"]) for chunk in batch],
        )


def run_pipeline() -> int:
    """Chạy load, chunk, embed và index; trả về số chunk đã index."""
    documents = load_documents()
    chunks = chunk_documents(documents)
    embedded_chunks = embed_chunks(chunks)
    index_to_vectorstore(embedded_chunks)
    print(f"Indexed {len(embedded_chunks)} chunks from {len(documents)} documents")
    return len(embedded_chunks)


if __name__ == "__main__":
    run_pipeline()
