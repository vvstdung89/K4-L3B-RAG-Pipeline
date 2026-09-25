"""Task 4: load standardized Markdown, chunk, embed, and persist in Chroma."""

from functools import lru_cache
import json
import math
import os
from pathlib import Path
import re
import tempfile
import unicodedata

from dotenv import load_dotenv

from .contracts import validate_document


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
STANDARDIZED_DIR = ROOT / "data" / "standardized"
CHROMA_DIR = ROOT / "chroma_db"
CHUNKS_PATH = ROOT / "data" / "chunks.jsonl"

# Character counts, not tokens. Paragraphs are preferred split boundaries.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CHUNKING_METHOD = "recursive"
EMBEDDING_BATCH_SIZE = 64
INDEX_BATCH_SIZE = 128
COLLECTION_NAME = "rag_documents"

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai").strip().lower()
_DEFAULT_MODELS = {
    "openai": "text-embedding-3-small",
    "gemini": "gemini-embedding-001",
    "sentence_transformers": "BAAI/bge-m3",
}
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "").strip() or _DEFAULT_MODELS.get(
    EMBEDDING_PROVIDER, ""
)
_DEFAULT_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "gemini-embedding-001": 3072,
    "BAAI/bge-m3": 1024,
}
EMBEDDING_DIM = int(
    os.getenv("EMBEDDING_DIM", "").strip()
    or _DEFAULT_DIMENSIONS.get(EMBEDDING_MODEL, 0)
)


def _validate_embedding_config() -> None:
    if EMBEDDING_PROVIDER not in _DEFAULT_MODELS:
        raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {EMBEDDING_PROVIDER}")
    if not EMBEDDING_MODEL or EMBEDDING_DIM <= 0:
        raise ValueError("Set EMBEDDING_MODEL and a positive EMBEDDING_DIM in .env")


@lru_cache(maxsize=3)
def _embedding_client(provider: str, model: str):
    if provider == "openai":
        from openai import OpenAI

        if not os.getenv("OPENAI_API_KEY", "").strip():
            raise RuntimeError("Missing OPENAI_API_KEY in .env")
        return OpenAI(timeout=60, max_retries=2)
    if provider == "gemini":
        from google import genai

        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("Missing GEMINI_API_KEY in .env")
        return genai.Client(api_key=key)
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            'Local embeddings require: python -m pip install -e ".[local]"'
        ) from exc
    return SentenceTransformer(model)


def _validate_vectors(vectors: list[list[float]], expected: int) -> None:
    if len(vectors) != expected:
        raise ValueError(f"Expected {expected} embeddings, received {len(vectors)}")
    for vector in vectors:
        if len(vector) != EMBEDDING_DIM:
            raise ValueError(f"Embedding dimension must be {EMBEDDING_DIM}")
        if not all(math.isfinite(value) for value in vector) or not any(vector):
            raise ValueError("Embedding must contain finite values and be nonzero")


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Shared document/query embedding function; one configured model and dimension."""
    if not texts:
        return []
    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("Embedding input must contain non-empty strings")
    _validate_embedding_config()
    client = _embedding_client(EMBEDDING_PROVIDER, EMBEDDING_MODEL)
    vectors = []
    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[start:start + EMBEDDING_BATCH_SIZE]
        if EMBEDDING_PROVIDER == "openai":
            options = {}
            if EMBEDDING_MODEL.startswith("text-embedding-3-"):
                options["dimensions"] = EMBEDDING_DIM
            response = client.embeddings.create(
                model=EMBEDDING_MODEL, input=batch, encoding_format="float", **options
            )
            ordered = sorted(response.data, key=lambda item: item.index)
            if [item.index for item in ordered] != list(range(len(batch))):
                raise ValueError("Embedding response has missing or duplicate indices")
            batch_vectors = [item.embedding for item in ordered]
        elif EMBEDDING_PROVIDER == "gemini":
            response = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=batch,
                config={"output_dimensionality": EMBEDDING_DIM},
            )
            batch_vectors = [item.values or [] for item in response.embeddings or []]
        else:
            batch_vectors = client.encode(
                batch, normalize_embeddings=True, show_progress_bar=False
            ).tolist()
        _validate_vectors(batch_vectors, len(batch))
        vectors.extend(batch_vectors)
    return vectors


@lru_cache(maxsize=4)
def _chroma_client(path: str):
    import chromadb
    from chromadb.config import Settings

    return chromadb.PersistentClient(
        path=path, settings=Settings(anonymized_telemetry=False)
    )


def get_collection():
    """Open the persistent cosine index and reject incompatible embedding spaces."""
    _validate_embedding_config()
    expected = {
        "hnsw:space": "cosine",
        "embedding_provider": EMBEDDING_PROVIDER,
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimension": EMBEDDING_DIM,
    }
    client = _chroma_client(str(CHROMA_DIR))
    names = {getattr(item, "name", item) for item in client.list_collections()}
    if COLLECTION_NAME in names:
        # Older Chroma versions overwrite metadata in get_or_create_collection.
        # Read without metadata first so a model change cannot bypass the guard.
        collection = client.get_collection(COLLECTION_NAME, embedding_function=None)
    else:
        collection = client.create_collection(
            name=COLLECTION_NAME,
            metadata={**expected, "hnsw:search_ef": 128},
            embedding_function=None,
        )
    metadata = collection.metadata or {}
    if any(metadata.get(key) != value for key, value in expected.items()):
        raise ValueError(
            "Existing Chroma collection uses a different embedding configuration. "
            "Restore the original .env settings or use a new CHROMA_DIR/COLLECTION_NAME."
        )
    return collection


def load_documents() -> list[dict]:
    """Read both source types, keeping header metadata out of retrieval text."""
    if not STANDARDIZED_DIR.is_dir():
        raise FileNotFoundError(f"Missing standardized directory: {STANDARDIZED_DIR}")
    documents = []
    for path in sorted(STANDARDIZED_DIR.rglob("*.md")):
        relative = path.relative_to(STANDARDIZED_DIR)
        if relative.parts[0] not in {"legal", "news"}:
            raise ValueError(f"Markdown must be under legal/ or news/: {relative}")
        text = path.read_text(encoding="utf-8-sig").strip()
        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else path.stem
        header, separator, body = text.partition("\n---\n")
        fields = dict(re.findall(r"^\*\*([^*]+):\*\*\s*(.+)$", header, re.MULTILINE))
        if separator and "Source" in fields:
            if not body.strip():
                raise ValueError(f"Empty document body: {relative}")
            content = f"# {title}\n\n{body.strip()}"
        else:
            fields = {}
            content = text
        source = fields.get("Source", "")
        url = source if source.startswith(("https://", "http://")) else None
        document = {
            "id": relative.as_posix(),
            "content": content,
            "metadata": {
                "source": (
                    fields.get("Source file")
                    or (source if not url else "")
                    or relative.as_posix()
                ),
                "title": fields.get("Title", title),
                "doc_type": relative.parts[0],
                "url": url,
            },
        }
        validate_document(document)
        documents.append(document)
    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Split by paragraph/sentence/word, with deterministic document-local IDs."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = []
    seen = set()
    for document in documents:
        validate_document(document)
        if document["id"] in seen:
            raise ValueError(f"Duplicate document ID: {document['id']}")
        seen.add(document["id"])
        text = unicodedata.normalize("NFC", document["content"])
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[^\S\n]+", " ", text)
        text = re.sub(r"\n(?: *\n)+", "\n\n", text).strip()
        for index, content in enumerate(splitter.split_text(text)):
            chunk = {
                "id": f"{document['id']}::chunk-{index}",
                "content": content,
                "metadata": {**document["metadata"], "chunk_index": index},
            }
            validate_document(chunk, require_chunk=True)
            chunks.append(chunk)
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Embed batches without mutating the input corpus."""
    for chunk in chunks:
        validate_document(chunk, require_chunk=True)
    embedded = []
    for start in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
        batch = chunks[start:start + EMBEDDING_BATCH_SIZE]
        vectors = embed_texts([chunk["content"] for chunk in batch])
        _validate_vectors(vectors, len(batch))
        embedded.extend(
            {**chunk, "embedding": vector} for chunk, vector in zip(batch, vectors)
        )
        print(f"Embedded {len(embedded)}/{len(chunks)} chunks", flush=True)
    return embedded


def index_to_vectorstore(chunks: list[dict]) -> None:
    """Upsert explicit embeddings by stable ID; never let Chroma embed implicitly."""
    if not chunks:
        return
    for chunk in chunks:
        validate_document(chunk, require_chunk=True)
    if len({chunk["id"] for chunk in chunks}) != len(chunks):
        raise ValueError("Duplicate chunk IDs")
    _validate_vectors([chunk["embedding"] for chunk in chunks], len(chunks))
    collection = get_collection()
    for start in range(0, len(chunks), INDEX_BATCH_SIZE):
        batch = chunks[start:start + INDEX_BATCH_SIZE]
        collection.upsert(
            ids=[chunk["id"] for chunk in batch],
            documents=[chunk["content"] for chunk in batch],
            embeddings=[chunk["embedding"] for chunk in batch],
            # Chroma's scalar metadata does not support None. An empty URL is
            # still valid under the public contract; JSONL retains literal null.
            metadatas=[
                {**chunk["metadata"], "url": chunk["metadata"]["url"] or ""}
                for chunk in batch
            ],
        )


def _save_chunks(chunks: list[dict]) -> None:
    CHUNKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=CHUNKS_PATH.parent, suffix=".tmp", delete=False
    ) as stream:
        temporary = Path(stream.name)
        for chunk in chunks:
            stream.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    try:
        os.replace(temporary, CHUNKS_PATH)
    finally:
        temporary.unlink(missing_ok=True)


def run_pipeline() -> None:
    """Index a complete corpus; remove obsolete chunks only after successful upsert."""
    documents = load_documents()
    chunks = chunk_documents(documents)
    if not chunks:
        raise ValueError("No chunks to index. Run src.task3_convert_markdown first.")
    collection = get_collection()  # Check model compatibility before API calls.
    print(
        f"Loaded {len(documents)} documents -> {len(chunks)} chunks "
        f"(size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})", flush=True
    )
    print(
        f"Embedding: {EMBEDDING_PROVIDER}/{EMBEDDING_MODEL}, {EMBEDDING_DIM} dimensions",
        flush=True,
    )
    embedded = embed_chunks(chunks)
    index_to_vectorstore(embedded)
    current_ids = {chunk["id"] for chunk in chunks}
    stale_ids = sorted(set(collection.get(include=[])["ids"]) - current_ids)
    for start in range(0, len(stale_ids), INDEX_BATCH_SIZE):
        collection.delete(ids=stale_ids[start:start + INDEX_BATCH_SIZE])
    _save_chunks(chunks)
    print(f"Indexed {collection.count()} chunks in {CHROMA_DIR}", flush=True)
    print(f"Saved shared chunk corpus to {CHUNKS_PATH}", flush=True)


if __name__ == "__main__":
    run_pipeline()
