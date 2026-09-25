"""Indexing checks using fake embeddings and a real temporary Chroma database."""

from copy import deepcopy
import json
import random
from types import SimpleNamespace

import pytest

from src import task4_chunking_indexing as indexing
from src.contracts import validate_document


def document(content="Vietnam tourism information. " * 60):
    return {
        "id": "legal/policy.md",
        "content": content,
        "metadata": {
            "source": "legal/policy.pdf",
            "title": "Tourism policy",
            "doc_type": "legal",
            "url": None,
        },
    }


@pytest.fixture
def isolated_index(tmp_path, monkeypatch):
    monkeypatch.setattr(indexing, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(indexing, "CHUNKS_PATH", tmp_path / "chunks.jsonl")
    monkeypatch.setattr(indexing, "EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr(indexing, "EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setattr(indexing, "EMBEDDING_DIM", 3)


def test_load_documents_preserves_utf8_metadata_and_excludes_header(tmp_path, monkeypatch):
    monkeypatch.setattr(indexing, "STANDARDIZED_DIR", tmp_path)
    for category in ("legal", "news"):
        (tmp_path / category).mkdir()
    (tmp_path / "legal" / "policy.md").write_text("# Luật du lịch\n\nĐiều 1. Nội dung.", encoding="utf-8")
    (tmp_path / "news" / "policy.md").write_text(
        "# Hạ Long\n\n**Title:** Du lịch Hạ Long\n\n"
        "**Source:** https://example.com/halong\n\n"
        "**Source file:** news/article.json\n\n"
        "**Crawled:** 2026-09-25\n\n---\n\nVịnh Hạ Long tại Quảng Ninh.",
        encoding="utf-8",
    )
    docs = indexing.load_documents()
    assert [item["id"] for item in docs] == ["legal/policy.md", "news/policy.md"]
    assert docs[0]["metadata"]["url"] is None
    assert docs[1]["metadata"] == {
        "source": "news/article.json", "title": "Du lịch Hạ Long",
        "doc_type": "news", "url": "https://example.com/halong",
    }
    assert "Vịnh Hạ Long" in docs[1]["content"]
    assert "**Crawled:**" not in docs[1]["content"]
    for item in docs:
        validate_document(item)
    (tmp_path / "legal" / "empty.md").write_text(" \n ", encoding="utf-8")
    with pytest.raises(ValueError, match="content"):
        indexing.load_documents()


def test_chunking_is_stable_bounded_and_non_mutating():
    docs = [document("Đoạn thứ nhất.   " * 100 + "\n\n\nĐoạn thứ hai. " * 100)]
    original = deepcopy(docs)
    chunks = indexing.chunk_documents(docs)
    assert chunks == indexing.chunk_documents(docs)
    assert docs == original
    assert len(chunks) > 1
    assert len({item["id"] for item in chunks}) == len(chunks)
    for position, item in enumerate(chunks):
        validate_document(item, require_chunk=True)
        assert len(item["content"]) <= indexing.CHUNK_SIZE
        assert item["metadata"]["chunk_index"] == position
        assert "   " not in item["content"]
        assert "\n\n\n" not in item["content"]
    with pytest.raises(ValueError, match="Duplicate document"):
        indexing.chunk_documents(docs + docs)


def test_openai_embedding_batches_and_restores_response_order(monkeypatch):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(data=[
            SimpleNamespace(index=i, embedding=[float(text), 1.0, 0.0])
            for i, text in reversed(list(enumerate(kwargs["input"])))
        ])

    monkeypatch.setattr(indexing, "EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr(indexing, "EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setattr(indexing, "EMBEDDING_DIM", 3)
    monkeypatch.setattr(indexing, "EMBEDDING_BATCH_SIZE", 2)
    monkeypatch.setattr(indexing, "_embedding_client", lambda *args: SimpleNamespace(
        embeddings=SimpleNamespace(create=create)
    ))
    assert indexing.embed_texts([]) == []
    assert indexing.embed_texts(["1", "2", "3"]) == [[1, 1, 0], [2, 1, 0], [3, 1, 0]]
    assert [len(call["input"]) for call in calls] == [2, 1]
    assert all(call["dimensions"] == 3 for call in calls)
    with pytest.raises(ValueError, match="non-empty"):
        indexing.embed_texts([" "])


@pytest.mark.parametrize("vector", [[1, 2], [float("nan"), 1, 0], [0, 0, 0]])
def test_invalid_embeddings_cannot_write_index(isolated_index, vector):
    chunk = indexing.chunk_documents([document("Short policy")])[0]
    with pytest.raises(ValueError):
        indexing.index_to_vectorstore([{**chunk, "embedding": vector}])
    assert not indexing.CHROMA_DIR.exists()


def test_upsert_is_idempotent_and_collection_rejects_different_model(isolated_index, monkeypatch):
    chunks = indexing.chunk_documents([document()])
    embedded = [{**chunk, "embedding": [1.0, 0.2, 0.3]} for chunk in chunks]
    indexing.index_to_vectorstore(embedded)
    indexing.index_to_vectorstore(embedded)
    collection = indexing.get_collection()
    assert collection.count() == len(chunks)
    assert collection.metadata["hnsw:space"] == "cosine"
    stored = collection.get(ids=[chunks[0]["id"]], include=["metadatas", "documents"])
    assert stored["metadatas"][0]["url"] == ""
    assert chunks[0]["metadata"]["url"] is None
    embedded[0]["content"] = "Updated policy content"
    indexing.index_to_vectorstore(embedded[:1])
    assert collection.get(ids=[chunks[0]["id"]])["documents"] == ["Updated policy content"]
    assert collection.count() == len(chunks)
    monkeypatch.setattr(indexing, "EMBEDDING_MODEL", "text-embedding-3-large")
    with pytest.raises(ValueError, match="different embedding configuration"):
        indexing.get_collection()


def test_full_reindex_removes_stale_chunks_only_after_embeddings_succeed(isolated_index, monkeypatch):
    docs = [document()]
    monkeypatch.setattr(indexing, "load_documents", lambda: docs)
    monkeypatch.setattr(indexing, "embed_texts", lambda texts: [[1, 0.2, 0.3] for _ in texts])
    indexing.run_pipeline()
    assert indexing.get_collection().count() > 1
    docs[0] = document("Shortened policy.")
    indexing.run_pipeline()
    assert indexing.get_collection().count() == 1
    corpus = [json.loads(line) for line in indexing.CHUNKS_PATH.read_text(encoding="utf-8").splitlines()]
    assert corpus == indexing.chunk_documents(docs)
    assert corpus[0]["metadata"]["url"] is None

    def unavailable(texts):
        raise RuntimeError("Embedding provider unavailable")

    monkeypatch.setattr(indexing, "embed_texts", unavailable)
    docs[0] = document("Replacement policy")
    with pytest.raises(RuntimeError, match="unavailable"):
        indexing.run_pipeline()
    assert indexing.get_collection().get()["documents"] == ["Shortened policy."]
    assert json.loads(indexing.CHUNKS_PATH.read_text(encoding="utf-8"))["content"] == "Shortened policy."


def test_hnsw_index_handles_more_than_the_in_memory_buffer(isolated_index, monkeypatch):
    # Older Chroma buffers fewer than 100 rows with brute-force search. Cross
    # that boundary to exercise the native HNSW code.
    monkeypatch.setattr(indexing, "EMBEDDING_DIM", 1536)
    chunks = []
    rng = random.Random(42)
    for i in range(128):
        vector = [rng.uniform(-1, 1) for _ in range(1536)]
        chunks.append({
            "id": f"policy::chunk-{i}", "content": f"Policy clause {i}",
            "metadata": {**document()["metadata"], "chunk_index": i},
            "embedding": vector,
        })
    indexing.index_to_vectorstore(chunks)
    indexing.index_to_vectorstore(chunks)
    collection = indexing.get_collection()
    assert collection.count() == 128
    result = collection.query(query_embeddings=[chunks[42]["embedding"]], n_results=1)
    assert result["ids"] == [["policy::chunk-42"]]
    assert result["distances"][0][0] == pytest.approx(0, abs=1e-6)
