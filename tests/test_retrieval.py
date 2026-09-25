"""Offline behavioral coverage for Tasks 7-9; no credentials or network needed."""

from copy import deepcopy

import pytest
import requests

from src import task7_reranking as fusion
from src import task8_pageindex_vectorless as pageindex
from src import task9_retrieval_pipeline as pipeline


def result(key="a", score=0.2, method="dense"):
    return {"id": key, "content": "Original source text", "score": score,
            "retrieval_method": method, "metadata": {
                "source": "news/article.json", "title": "Du lịch Việt Nam",
                "doc_type": "news", "url": "https://example.org/article", "chunk_index": 0}}


def test_rrf_ignores_raw_scale_deduplicates_and_does_not_mutate():
    dense = [result("a", -0.1), result("a", -0.1), result("b", -0.9)]
    sparse = [result("b", 10000, "bm25")]
    before = deepcopy([dense, sparse])
    output = fusion.rerank_rrf([dense, sparse], top_k=10, k=0)
    assert [(item["id"], item["score"]) for item in output] == [("b", 1.5), ("a", 1)]
    output[0]["metadata"]["title"] = "Changed"
    assert [dense, sparse] == before


def test_rrf_ties_are_stable_and_empty_is_empty():
    assert fusion.rerank_rrf([[], []]) == []
    assert [item["id"] for item in fusion.rerank_rrf([[result("b")], [result("a")]])] == ["a", "b"]
    assert fusion.rerank_rrf([[result()]], top_k=0) == []


@pytest.mark.parametrize("kwargs", [{"k": -1}, {"k": True}, {"top_k": 1.5}])
def test_rrf_rejects_invalid_parameters(kwargs):
    with pytest.raises((ValueError, TypeError)):
        fusion.rerank_rrf([], **kwargs)


@pytest.fixture
def cached_source(monkeypatch, tmp_path):
    document = {key: value for key, value in result().items() if key in {"id", "content", "metadata"}}
    document["metadata"].pop("chunk_index")
    monkeypatch.setattr(pageindex, "PAGEINDEX_API_KEY", "test-key")
    monkeypatch.setattr(pageindex, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(pageindex, "PDF_DIR", tmp_path / "pdfs")
    monkeypatch.setattr(pageindex, "load_documents", lambda: [document])
    cache = {"version": 1, "account": pageindex._account(), "documents": {"a": {
        "doc_id": "pi-test", "fingerprint": pageindex._fingerprint(document),
        "filename": "source.pdf", "status": "completed"}}}
    pageindex._write_cache(cache)
    return document, cache


def test_pageindex_fetches_original_cited_pages_not_generated_answer(monkeypatch, cached_source):
    calls = []

    def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if method == "POST":
            assert kwargs["json"]["doc_id"] == ["pi-test"]
            assert kwargs["json"]["enable_citations"] is True
            return {"choices": [{"message": {"content": (
                "Generated answer <doc=unknown.pdf;page=1> "
                "<doc=source.pdf;page=2;block=p2_text_3> "
                "<doc=source.pdf;page=2> <doc=source.pdf;page=0> "
                "<doc=source.pdf;page=9> <doc=source.pdf;page=1>"
            )}}]}
        assert kwargs["params"] == {"type": "ocr", "format": "page"}
        return {"status": "completed", "result": [
            {"page_index": 1, "markdown": "First original page"},
            {"page_index": 2, "markdown": "Second original page"}]}

    monkeypatch.setattr(pageindex, "_request", request)
    output = pageindex.pageindex_search("du lịch", top_k=5)
    assert len(calls) == 2
    assert [item["content"] for item in output] == ["Second original page", "First original page"]
    assert [item["score"] for item in output] == [1, 0.5]
    assert output[0]["metadata"]["chunk_index"] == 1
    assert output[0]["metadata"]["source"] == "news/article.json"
    assert output[0]["metadata"]["url"] == "https://example.org/article"
    assert output[0]["retrieval_method"] == "pageindex"


def test_pageindex_no_citations_means_no_evidence(monkeypatch, cached_source):
    monkeypatch.setattr(pageindex, "_request", lambda *a, **kw: {
        "choices": [{"message": {"content": "No supporting sources."}}]})
    assert pageindex.pageindex_search("unknown") == []


def test_pageindex_top_k_limits_ocr_calls(monkeypatch, cached_source):
    def request(method, path, **kwargs):
        if method == "POST":
            return {"choices": [{"message": {"content": "<doc=source.pdf;page=1><doc=source.pdf;page=2>"}}]}
        return {"status": "completed", "result": [
            {"page_index": 1, "markdown": "First"}, {"page_index": 2, "markdown": "Second"}]}
    monkeypatch.setattr(pageindex, "_request", request)
    assert len(pageindex.pageindex_search("query", top_k=1)) == 1


def test_pageindex_ocr_timeout_returns_no_fabricated_evidence(monkeypatch, cached_source):
    def request(method, path, **kwargs):
        if method == "POST":
            return {"choices": [{"message": {"content": "<doc=source.pdf;page=1>"}}]}
        raise requests.Timeout()
    monkeypatch.setattr(pageindex, "_request", request)
    assert pageindex.pageindex_search("query") == []


def test_stale_cache_is_excluded_from_search(monkeypatch, cached_source):
    cached_source[0]["content"] += " updated"
    monkeypatch.setattr(pageindex, "_request", lambda *a, **kw: pytest.fail("No network for stale sources"))
    with pytest.raises(RuntimeError, match="No current"):
        pageindex.pageindex_search("query")


def test_cache_cannot_cross_accounts(monkeypatch, cached_source):
    monkeypatch.setattr(pageindex, "PAGEINDEX_API_KEY", "other-key")
    with pytest.raises(ValueError, match="another API key"):
        pageindex._read_cache()


def test_upload_reuses_ids_and_replaces_changed_source(monkeypatch, cached_source):
    calls = []
    monkeypatch.setattr(pageindex, "_to_pdf", lambda doc, path: (
        path.parent.mkdir(exist_ok=True), path.write_bytes(b"%PDF-1.4 test")))

    def request(method, path, **kwargs):
        calls.append(method)
        if method == "POST":
            assert kwargs["files"]["file"][2] == "application/pdf"
            return {"doc_id": "pi-new"}
        return {"status": "completed"}

    monkeypatch.setattr(pageindex, "_request", request)
    pageindex.upload_documents()
    assert calls == []
    cached_source[0]["content"] += " changed"
    pageindex.upload_documents()
    assert calls == ["POST", "GET"]
    assert pageindex._read_cache()["documents"]["a"]["doc_id"] == "pi-new"
    pageindex.upload_documents()
    assert calls == ["POST", "GET"]
    assert "test-key" not in pageindex.CACHE_PATH.read_text()


def test_upload_preserves_id_on_processing_timeout_then_resumes(monkeypatch, cached_source):
    document, cache = cached_source
    cache["documents"] = {}
    pageindex._write_cache(cache)
    monkeypatch.setattr(pageindex, "_to_pdf", lambda doc, path: (
        path.parent.mkdir(exist_ok=True), path.write_bytes(b"%PDF-1.4 test")))
    calls = []

    def request(method, path, **kwargs):
        calls.append(method)
        if method == "POST":
            return {"doc_id": "pi-pending"}
        raise TimeoutError()

    monkeypatch.setattr(pageindex, "_request", request)
    with pytest.raises(TimeoutError):
        pageindex.upload_documents()
    assert pageindex._read_cache()["documents"]["a"]["doc_id"] == "pi-pending"
    monkeypatch.setattr(pageindex, "_request", lambda method, *a, **kw: (
        calls.append(method) or {"status": "completed"}))
    pageindex.upload_documents()
    assert calls == ["POST", "GET", "GET"]


def test_http_timeout_and_auth_are_explicit(monkeypatch):
    monkeypatch.setattr(pageindex, "PAGEINDEX_API_KEY", "test-key")
    monkeypatch.setattr(pageindex.time, "monotonic", lambda: 10)

    def request(method, url, **kwargs):
        assert kwargs["timeout"] == 5
        assert kwargs["headers"] == {"api_key": "test-key"}
        assert url == "https://api.pageindex.ai/doc/"
        raise requests.Timeout()

    monkeypatch.setattr(pageindex.requests, "request", request)
    with pytest.raises(requests.Timeout):
        pageindex._request("GET", "/doc/", deadline=15)
    with pytest.raises(TimeoutError):
        pageindex._request("GET", "/doc/", deadline=10)


def test_missing_key_and_empty_queries_never_call_network(monkeypatch):
    monkeypatch.setattr(pageindex, "PAGEINDEX_API_KEY", "")
    monkeypatch.setattr(pageindex.requests, "request", lambda *a, **kw: pytest.fail("Unexpected request"))
    assert pageindex.pageindex_search("  ") == []
    assert pageindex.pageindex_search("query", top_k=0) == []
    with pytest.raises(RuntimeError, match="PAGEINDEX_API_KEY"):
        pageindex.upload_documents()
    with pytest.raises(RuntimeError, match="PAGEINDEX_API_KEY"):
        pageindex.pageindex_search("query")


def test_pdf_preserves_vietnamese_and_normalizes_legacy_bullet(tmp_path):
    pdfplumber = pytest.importorskip("pdfplumber")
    document = {"content": "# Du lịch Việt Nam\n\nĐiều kiện lữ hành quốc tế\n\uf0b7 Nội dung gốc",
                "metadata": {"title": "Du lịch Việt Nam"}}
    path = tmp_path / "source.pdf"
    pageindex._to_pdf(document, path)
    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert "Điều kiện lữ hành quốc tế" in text
    assert "• Nội dung gốc" in text


@pytest.fixture
def retrieval_sources(monkeypatch):
    monkeypatch.setattr(pipeline, "semantic_search", lambda *a, **kw: [result(score=0.3)])
    monkeypatch.setattr(pipeline, "lexical_search", lambda *a, **kw: [result("b", 100, "bm25")])
    monkeypatch.setattr(pipeline, "pageindex_search", lambda *a, **kw: [])


def test_equal_threshold_does_not_fallback(monkeypatch, retrieval_sources):
    monkeypatch.setattr(pipeline, "pageindex_search", lambda *a, **kw: pytest.fail("Unexpected fallback"))
    assert pipeline.retrieve("query", score_threshold=0.3)[0]["retrieval_method"] == "hybrid"


def test_dense_only_ablation_skips_bm25_and_rrf(monkeypatch, retrieval_sources):
    monkeypatch.setattr(pipeline, "lexical_search", lambda *a, **kw: pytest.fail("BM25 in dense-only"))
    monkeypatch.setattr(pipeline, "rerank_rrf", lambda *a, **kw: pytest.fail("RRF in dense-only"))
    assert pipeline.retrieve("query", use_reranking=False) == [result(score=0.3)]


def test_dense_failure_preserves_bm25_and_attempts_fallback(monkeypatch, retrieval_sources):
    def unavailable(*args, **kwargs):
        raise requests.Timeout()
    monkeypatch.setattr(pipeline, "semantic_search", unavailable)
    calls = []
    monkeypatch.setattr(pipeline, "pageindex_search", lambda *a, **kw: calls.append(1) or [])
    output = pipeline.retrieve("query", score_threshold=-1)
    assert calls == [1]
    assert output[0]["id"] == "b"
    assert output[0]["retrieval_method"] == "hybrid"


def test_malformed_fallback_preserves_hybrid(monkeypatch, retrieval_sources):
    monkeypatch.setattr(pipeline, "pageindex_search", lambda *a, **kw: [{"bad": "response"}])
    assert pipeline.retrieve("query", score_threshold=0.5)[0]["retrieval_method"] == "hybrid"


@pytest.mark.parametrize("threshold", [float("nan"), float("inf"), 1.1, -1.1, True])
def test_threshold_validation(threshold):
    with pytest.raises(ValueError):
        pipeline.retrieve("query", score_threshold=threshold)


def test_blank_query_short_circuits(monkeypatch):
    monkeypatch.setattr(pipeline, "semantic_search", lambda *a, **kw: pytest.fail("Unexpected search"))
    assert pipeline.retrieve("  ") == []
    assert pipeline.retrieve("query", top_k=0) == []
