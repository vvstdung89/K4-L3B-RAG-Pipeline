"""Search contracts and corpus consistency, without network/API calls."""

from copy import deepcopy
import json
import unicodedata

import pytest

from src import task4_chunking_indexing as indexing
from src import task5_semantic_search as semantic
from src import task6_lexical_search as lexical
from src.contracts import validate_search_results


def chunk(item_id, content):
    return {
        "id": item_id,
        "content": content,
        "metadata": {
            "source": f"{item_id}.md", "title": item_id,
            "doc_type": "news", "url": None, "chunk_index": 0,
        },
    }


@pytest.fixture(autouse=True)
def isolate_search(monkeypatch, tmp_path):
    def unexpected(*args, **kwargs):
        pytest.fail("Unexpected database/API access")

    monkeypatch.setattr(semantic, "embed_texts", unexpected)
    monkeypatch.setattr(semantic, "get_collection", unexpected)
    monkeypatch.setattr(lexical, "CORPUS", None)
    monkeypatch.setattr(lexical, "CHUNKS_PATH", tmp_path / "chunks.jsonl")
    lexical._read_corpus.cache_clear()
    lexical._build_index.cache_clear()


@pytest.mark.parametrize("search", [semantic.semantic_search, lexical.lexical_search])
@pytest.mark.parametrize("query, top_k", [("", 3), (" \n\t ", 3), ("policy", 0), ("policy", -2)])
def test_empty_requests_do_not_read_corpus_or_call_api(search, query, top_k):
    assert search(query, top_k=top_k) == []


@pytest.mark.parametrize("search", [semantic.semantic_search, lexical.lexical_search])
@pytest.mark.parametrize("query, top_k", [(None, 3), ("policy", 2.5), ("policy", True)])
def test_invalid_arguments_are_rejected(search, query, top_k):
    with pytest.raises(TypeError):
        search(query, top_k=top_k)


def test_semantic_empty_collection_avoids_embedding(monkeypatch):
    class EmptyCollection:
        def count(self):
            return 0

    monkeypatch.setattr(semantic, "get_collection", EmptyCollection)
    assert semantic.semantic_search("policy") == []


def test_semantic_caps_top_k_sorts_and_preserves_raw_cosine(monkeypatch):
    metadata = {**chunk("policy", "content")["metadata"], "url": ""}

    class FakeCollection:
        def count(self):
            return 3

        def query(self, **kwargs):
            assert kwargs["n_results"] == 3
            assert kwargs["query_embeddings"] == [[1.0, 0.0]]
            assert kwargs["include"] == ["documents", "metadatas", "distances"]
            return {
                "ids": [["low", "high", "middle"]],
                "documents": [["Opposite meaning", "Exact meaning", "Some similarity"]],
                "metadatas": [[metadata, metadata, metadata]],
                "distances": [[1.2, 0.1, 0.5]],
            }

    def embed(texts):
        assert texts == ["policy"]
        return [[1.0, 0.0]]

    monkeypatch.setattr(semantic, "get_collection", FakeCollection)
    monkeypatch.setattr(semantic, "embed_texts", embed)
    results = semantic.semantic_search(" policy ", top_k=50)
    assert [item["id"] for item in results] == ["high", "middle", "low"]
    assert [item["score"] for item in results] == pytest.approx([0.9, 0.5, -0.2])
    assert results[0]["metadata"]["url"] is None
    assert metadata["url"] == ""
    validate_search_results(results, top_k=50, expected_method="dense")


def test_semantic_provider_failure_is_not_disguised_as_no_matches(monkeypatch):
    class Collection:
        def count(self):
            return 1

    def unavailable(texts):
        raise RuntimeError("Embedding provider unavailable")

    monkeypatch.setattr(semantic, "get_collection", Collection)
    monkeypatch.setattr(semantic, "embed_texts", unavailable)
    with pytest.raises(RuntimeError, match="unavailable"):
        semantic.semantic_search("policy")


def test_bm25_single_document_and_unknown_terms(monkeypatch):
    monkeypatch.setattr(lexical, "CORPUS", [chunk("one", "Vietnam tourism policy")])
    results = lexical.lexical_search("tourism", top_k=10)
    assert len(results) == 1 and results[0]["score"] > 0
    assert lexical.lexical_search("astronomy") == []
    assert lexical.lexical_search("?!") == []
    monkeypatch.setattr(lexical, "CORPUS", [])
    assert lexical.lexical_search("tourism") == []
    monkeypatch.setattr(lexical, "CORPUS", [chunk("punctuation", "--- !!!")])
    assert lexical.lexical_search("tourism") == []


def test_bm25_vietnamese_unicode_and_exact_document_codes(monkeypatch):
    corpus = [
        chunk("halong", "Vịnh Hạ Long, Quảng Ninh."),
        chunk("law", "Luật du lịch số 09/2017/QH14."),
        chunk("other", "Văn bản số 09/2018/QH14."),
    ]
    monkeypatch.setattr(lexical, "CORPUS", corpus)
    query = unicodedata.normalize("NFD", "HẠ LONG!")
    assert lexical.lexical_search(query)[0]["id"] == "halong"
    assert [item["id"] for item in lexical.lexical_search("09/2017/QH14")] == ["law"]


def test_bm25_ties_are_stable_and_results_cannot_mutate_corpus(monkeypatch):
    corpus = [chunk("b", "tourism policy"), chunk("a", "tourism policy")]
    original = deepcopy(corpus)
    monkeypatch.setattr(lexical, "CORPUS", corpus)
    results = lexical.lexical_search("tourism", top_k=1)
    assert [item["id"] for item in results] == ["a"]
    results[0]["metadata"]["title"] = "Modified"
    assert corpus == original
    # Rebuild after an in-place content update, even though the corpus object is unchanged.
    corpus[0]["content"] = "astronomy"
    assert lexical.lexical_search("astronomy")[0]["id"] == "b"


def test_bm25_loads_export_and_refreshes_after_reindex():
    path = lexical.CHUNKS_PATH
    first = chunk("first", "tourism policy")
    path.write_text(json.dumps(first) + "\n", encoding="utf-8")
    assert lexical.lexical_search("tourism")[0]["id"] == "first"
    assert lexical.lexical_search("tourism")[0]["id"] == "first"
    assert lexical._read_corpus.cache_info().hits == 1
    assert lexical._build_index.cache_info().hits == 1
    second = chunk("replacement", "astronomy and distant planets")
    path.write_text(json.dumps(second) + "\n", encoding="utf-8")
    assert lexical.lexical_search("tourism") == []
    assert lexical.lexical_search("astronomy")[0]["id"] == "replacement"


def test_bm25_reports_missing_corrupt_and_duplicate_corpus():
    path = lexical.CHUNKS_PATH
    with pytest.raises(FileNotFoundError, match="task4_chunking_indexing"):
        lexical.lexical_search("tourism")
    path.write_text("{broken json}\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"chunks.jsonl:1"):
        lexical.lexical_search("tourism")
    line = json.dumps(chunk("duplicate", "tourism")) + "\n"
    path.write_text(line * 2, encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate chunk ID"):
        lexical.lexical_search("tourism")


def test_both_searches_use_identical_indexed_content_and_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(indexing, "CHROMA_DIR", tmp_path / "chroma")
    monkeypatch.setattr(indexing, "EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr(indexing, "EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setattr(indexing, "EMBEDDING_DIM", 3)
    corpus = [chunk("tourism", "Vietnam tourism"), chunk("astronomy", "Distant planets")]
    indexing.index_to_vectorstore([
        {**corpus[0], "embedding": [1.0, 0.0, 0.0]},
        {**corpus[1], "embedding": [0.0, 1.0, 0.0]},
    ])
    lexical.CHUNKS_PATH.write_text(
        "\n".join(json.dumps(item) for item in corpus), encoding="utf-8"
    )
    monkeypatch.setattr(semantic, "get_collection", indexing.get_collection)
    monkeypatch.setattr(semantic, "embed_texts", lambda texts: [[1.0, 0.0, 0.0]])
    dense = semantic.semantic_search("tourism", top_k=1)
    sparse = lexical.lexical_search("tourism", top_k=1)
    for key in ("id", "content", "metadata"):
        assert dense[0][key] == sparse[0][key] == corpus[0][key]
    validate_search_results(dense, top_k=1, expected_method="dense")
    validate_search_results(sparse, top_k=1, expected_method="bm25")
