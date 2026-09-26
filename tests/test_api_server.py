"""UI adapter checks: no provider calls, reindexing, or task mutations."""

from copy import deepcopy
from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

from src import api_server as api
from src import task9_retrieval_pipeline as retrieval


@pytest.fixture
def client():
    return TestClient(api.app)


@pytest.fixture
def chunks():
    return [
        {"id": f"legal/example.md::chunk-{i}", "content": f"Evidence {i}",
         "score": 0.9 - i * 0.1, "retrieval_method": "dense",
         "metadata": {"title": "Example", "source": "example.md", "doc_type": "legal",
                      "url": None, "chunk_index": i}}
        for i in range(4)
    ]


@pytest.mark.parametrize("reranking", [True, False])
@pytest.mark.parametrize("threshold", [0.3, 0.95])
def test_trace_matches_existing_retrieval(monkeypatch, chunks, reranking, threshold):
    sparse = [{**chunk, "retrieval_method": "bm25"} for chunk in reversed(chunks)]
    fallback = [{**chunks[0], "retrieval_method": "pageindex"}]
    for module in (api, retrieval):
        monkeypatch.setattr(module, "semantic_search", lambda *a, **k: deepcopy(chunks))
        monkeypatch.setattr(module, "lexical_search", lambda *a, **k: deepcopy(sparse))
    monkeypatch.setattr(api.pageindex, "pageindex_search", lambda *a, **k: deepcopy(fallback))
    monkeypatch.setattr(retrieval, "pageindex_search", lambda *a, **k: deepcopy(fallback))
    traced = api.trace_retrieval("question", 3, reranking, threshold)
    expected = retrieval.retrieve("question", 3, threshold, reranking)
    assert traced["chunks"] == expected
    assert traced["fallback"]["used"] == (threshold > 0.9)
    assert traced["dense"][0]["score"] == 0.9


def test_chat_citations_follow_reordered_context(client, monkeypatch, chunks):
    monkeypatch.setattr(api, "_require_index", lambda: None)
    monkeypatch.setattr(api, "semantic_search", lambda *a, **k: deepcopy(chunks))
    monkeypatch.setattr(api, "lexical_search", lambda *a, **k: [])
    llm = Mock(return_value="Answer [Document 2, Document 3].")
    monkeypatch.setattr(api, "call_llm", llm)
    response = client.post('/api/chat', json={"query": "question", "top_k": 4, "use_reranking": False})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Answer [2][3]."
    assert body["cited"] == [2, 3]
    assert [source["id"] for source in body["sources"]] == [chunks[i]["id"] for i in (0, 3, 1, 2)]
    assert [source["id"] for source in body["final"]] == [chunk["id"] for chunk in chunks]
    assert body["sources"][1]["cited"] is True
    assert body["sources"][1]["dense_rank"] == 4
    assert body["sources"][1]["dense_score"] == chunks[3]["score"]
    prompt = llm.call_args.args[1]
    assert prompt.index('Evidence 3') < prompt.index('Evidence 1')
    assert llm.call_count == 1


def test_empty_index_returns_actionable_error_without_provider_calls(client, monkeypatch):
    monkeypatch.setattr(api.indexing, "get_collection", lambda: Mock(count=lambda: 0))
    search = Mock(side_effect=AssertionError("Provider must not be called"))
    monkeypatch.setattr(api, "semantic_search", search)
    for route in ("chat", "retrieve"):
        response = client.post(f"/api/{route}", json={"query": "question"})
        assert response.status_code == 409
        assert "src.task4_chunking_indexing" in response.json()["detail"]
    search.assert_not_called()


@pytest.mark.parametrize("payload", [{"query": " "}, {"query": "x", "top_k": 0},
                                    {"query": "x", "score_threshold": 2}])
def test_invalid_query_settings_are_rejected(client, payload):
    assert client.post('/api/chat', json=payload).status_code == 422


def test_saved_evaluation_preserves_metrics_and_missing_measurements(client, monkeypatch):
    read_json = api._read_json
    monkeypatch.setattr(api, '_read_json', lambda path: None if path.name == 'demo_eval_results.json' else read_json(path))
    saved = api._read_json(api.PROJECT_ROOT / 'reports' / 'gemini_eval_results.json')
    body = client.get('/api/evaluation').json()
    assert body["summary"]["method"] == "Gemini LLM judge"
    assert len(body["runs"]["A_dense"]) == 15
    assert len(body["runs"]["B_hybrid_rrf"]) == 15
    assert body["summary"]["configs"]["A_dense"]["answer_relevancy"] == saved["scores"]["A_dense_only"]["answer_relevance"]
    assert body["summary"]["configs"]["B_hybrid_rrf"]["latency_ms_mean"] is None
    assert body["runs"]["A_dense"][0]["hit_expected_source"] is None


def test_demo_evaluation_uses_current_method_and_measured_latency(client, monkeypatch):
    read_json = api._read_json
    saved = read_json(api.PROJECT_ROOT / 'reports' / 'gemini_eval_results.json')
    saved['evaluation_method'] = 'OpenAI LLM judge'
    for row in saved['cases']:
        row['latency_ms'] = 1234.0
    monkeypatch.setattr(api, '_read_json', lambda path: saved if path.name == 'demo_eval_results.json' else read_json(path))
    body = client.get('/api/evaluation').json()
    assert body['summary']['method'] == 'OpenAI LLM judge'
    assert body['summary']['artifact'] == 'reports/demo_eval_results.json'
    assert body['summary']['configs']['A_dense']['latency_ms_mean'] == 1234.0
    assert body['runs']['B_hybrid_rrf'][0]['latency_ms'] == 1234.0


def test_document_endpoint_blocks_path_escape(client):
    assert client.get('/api/documents/markdown', params={"doc_id": "../../.env"}).status_code == 404


def test_generation_error_is_redacted(client, monkeypatch, chunks):
    monkeypatch.setattr(api, "_require_index", lambda: None)
    monkeypatch.setattr(api, "semantic_search", lambda *a, **k: deepcopy(chunks))
    monkeypatch.setattr(api, "lexical_search", lambda *a, **k: [])
    monkeypatch.setattr(api, "call_llm", Mock(side_effect=RuntimeError("secret provider response")))
    response = client.post('/api/chat', json={"query": "question"})
    body = response.json()
    assert body["refused"] is True
    assert body["sources"] == []
    assert body["error"] == "RuntimeError"
    assert "secret" not in response.text


def test_paraphrased_refusal_does_not_display_unused_sources(client, monkeypatch, chunks):
    monkeypatch.setattr(api, "_require_index", lambda: None)
    monkeypatch.setattr(api, "semantic_search", lambda *a, **k: deepcopy(chunks))
    monkeypatch.setattr(api, "lexical_search", lambda *a, **k: [])
    monkeypatch.setattr(api, "call_llm", lambda *a: "Tôi không thể xác minh thông tin về cách làm bánh từ các tài liệu đã cung cấp.")
    body = client.post('/api/chat', json={"query": "Bake a cake"}).json()
    assert body['refused'] is True
    assert body['sources'] == []
    assert body['retrieval_source'] == 'none'
    assert body['answer'] == api.REFUSAL_MESSAGE
