"""
Backend FastAPI cho UI React (src/src). Mọi dữ liệu lấy từ data/, ChromaDB và
reports/gemini_eval_results.json — không có dữ liệu mẫu.

Chạy:
    python -m src.api_server            # http://127.0.0.1:8000
    cd src && npm run dev               # Vite proxy /api sang cổng 8000
"""

import json
import os
import re
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from . import task4_chunking_indexing as indexing  # noqa: E402
from . import task8_pageindex_vectorless as pageindex  # noqa: E402
from .task5_semantic_search import semantic_search  # noqa: E402
from .task6_lexical_search import lexical_search  # noqa: E402
from .task7_reranking import rerank_rrf  # noqa: E402
from .task9_retrieval_pipeline import SCORE_THRESHOLD  # noqa: E402
from .task10_generation import (  # noqa: E402
    SAFE_REFUSAL as REFUSAL_MESSAGE,
    LLM_MODEL,
    LLM_PROVIDER,
    SYSTEM_PROMPT,
    TEMPERATURE,
    TOP_K,
    TOP_P,
    call_llm,
    format_context,
    reorder_for_llm,
)


LANDING_DIR = PROJECT_ROOT / "data" / "landing"
STANDARDIZED_DIR = indexing.STANDARDIZED_DIR
EVAL_DIR = PROJECT_ROOT / "group_project" / "evaluation"
RRF_K = 60
CANDIDATE_MULTIPLIER = 2

app = FastAPI(title="Du Lịch Việt RAG API")


def _display_answer(answer: str) -> str:
    """Render task10's [Document N] labels as clickable UI citations."""
    return re.sub(
        r"\[Document\s+\d+(?:\s*,\s*(?:Document\s+)?\d+)*\]",
        lambda match: "".join(f"[{number}]" for number in re.findall(r"\d+", match[0])),
        answer,
    )


def _pageindex_configured() -> bool:
    return bool(pageindex.PAGEINDEX_API_KEY.strip())


def _is_refusal(answer: str) -> bool:
    normalized = unicodedata.normalize("NFC", answer).strip().casefold()
    return (REFUSAL_MESSAGE.rstrip(".").casefold() in normalized
            or normalized.startswith(("tôi không thể xác minh", "i cannot verify")))


def _model_label() -> tuple[str, str]:
    # Display the same provider defaults used by task10.call_llm.
    provider = LLM_PROVIDER.lower()
    defaults = {"openai": "gpt-4o-mini", "gemini": "gemini-2.5-flash",
                "anthropic": "claude-3-5-haiku-latest"}
    return provider, LLM_MODEL or defaults.get(provider, "")


def _require_index() -> None:
    if not indexing.get_collection().count():
        raise HTTPException(409, "Chưa có vector index. Chạy python -m src.task4_chunking_indexing trước khi hỏi đáp.")


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _chunk_counts() -> Counter:
    """Số chunk trong Chroma theo document id (phần trước '::chunk-')."""
    ids = indexing.get_collection().get(include=[])["ids"]
    return Counter(_nfc(item_id.split("::chunk-")[0]) for item_id in ids)


def _landing_file(relative: Path) -> Path | None:
    folder = LANDING_DIR / relative.parent
    for candidate in folder.glob(f"{relative.stem}.*"):
        if _nfc(candidate.stem) == _nfc(relative.stem):
            return candidate
    return None


def _brief(result: dict, rank: int) -> dict:
    return {
        "rank": rank,
        "id": result["id"],
        "score": round(float(result["score"]), 6),
        "retrieval_method": result["retrieval_method"],
        "title": result["metadata"].get("title", ""),
        "source": result["metadata"].get("source", ""),
        "doc_type": result["metadata"].get("doc_type", ""),
        "url": result["metadata"].get("url"),
        "chunk_index": result["metadata"].get("chunk_index"),
        "content": result["content"],
    }


def trace_retrieval(query: str, top_k: int, use_reranking: bool, score_threshold: float) -> dict:
    """Giống task9.retrieve nhưng giữ lại kết quả trung gian và thời gian từng bước."""
    timings: dict[str, float] = {}
    candidates = top_k * CANDIDATE_MULTIPLIER

    start = time.perf_counter()
    dense = semantic_search(query, top_k=candidates)
    timings["dense_ms"] = (time.perf_counter() - start) * 1000

    # Match main's task9: BM25 is called in both modes; only fusion is optional.
    start = time.perf_counter()
    sparse = lexical_search(query, top_k=candidates)
    timings["bm25_ms"] = (time.perf_counter() - start) * 1000
    if use_reranking:
        start = time.perf_counter()
        ranked = rerank_rrf([dense, sparse], top_k=top_k, k=RRF_K)
        timings["rrf_ms"] = (time.perf_counter() - start) * 1000
    else:
        ranked = dense[:top_k]

    best_dense_score = dense[0]["score"] if dense else 0.0
    fallback = {"triggered": best_dense_score < score_threshold, "configured": _pageindex_configured(),
                "used": False, "error": None}
    final = ranked[:top_k]
    if fallback["triggered"]:
        start = time.perf_counter()
        try:
            results = pageindex.pageindex_search(query, top_k=top_k)
            if results:
                final = results[:top_k]
                fallback["used"] = True
        except Exception as error:
            fallback["error"] = type(error).__name__
        timings["pageindex_ms"] = (time.perf_counter() - start) * 1000

    dense_rank = {item["id"]: index for index, item in enumerate(dense, 1)}
    bm25_rank = {item["id"]: index for index, item in enumerate(sparse, 1)}
    dense_score = {item["id"]: item["score"] for item in dense}
    final_out = []
    for index, item in enumerate(final, 1):
        brief = _brief(item, index)
        brief["dense_rank"] = dense_rank.get(item["id"])
        brief["bm25_rank"] = bm25_rank.get(item["id"])
        brief["dense_score"] = dense_score.get(item["id"])
        final_out.append(brief)

    return {
        "query": query,
        "top_k": top_k,
        "use_reranking": use_reranking,
        "score_threshold": score_threshold,
        "best_dense_score": best_dense_score,
        "dense": [_brief(item, index) for index, item in enumerate(dense, 1)],
        "bm25": [_brief(item, index) for index, item in enumerate(sparse, 1)],
        "final": final_out,
        "chunks": final,
        "retrieval_source": final[0]["retrieval_method"] if final else "none",
        "fallback": fallback,
        "timings": {key: round(value, 1) for key, value in timings.items()},
    }


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1, pattern=r"\S")
    top_k: int = Field(default=TOP_K, ge=1, le=20)
    use_reranking: bool = True
    score_threshold: float | None = Field(default=None, ge=-1, le=1)


@app.get("/api/config")
def get_config() -> dict:
    provider, model = _model_label()
    collection = indexing.get_collection()
    return {
        "llm_provider": provider,
        "llm_model": model,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "top_k": TOP_K,
        "candidate_multiplier": CANDIDATE_MULTIPLIER,
        "rrf_k": RRF_K,
        "score_threshold": SCORE_THRESHOLD,
        "embedding_provider": os.getenv("EMBEDDING_PROVIDER", "sentence_transformers"),
        "embedding_model": os.getenv("EMBEDDING_MODEL", indexing.EMBEDDING_MODEL),
        "embedding_dim": indexing.EMBEDDING_DIM,
        "chunk_size": indexing.CHUNK_SIZE,
        "chunk_overlap": indexing.CHUNK_OVERLAP,
        "chunking_method": indexing.CHUNKING_METHOD,
        "collection_name": indexing.COLLECTION_NAME,
        "collection_count": collection.count(),
        "distance": (collection.metadata or {}).get("hnsw:space", "cosine"),
        "pageindex_configured": _pageindex_configured(),
        "api_keys": {
            name: bool(os.getenv(name))
            for name in ("OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "PAGEINDEX_API_KEY")
        },
        "system_prompt": SYSTEM_PROMPT,
        "refusal_message": REFUSAL_MESSAGE,
    }


@app.get("/api/documents")
def list_documents() -> dict:
    counts = _chunk_counts()
    documents = []
    for document in indexing.load_documents():
        relative = Path(document["id"])
        path = STANDARDIZED_DIR / relative
        doc_id = _nfc(relative.as_posix())
        metadata = document["metadata"]
        title, url, content = metadata["title"], metadata["url"], document["content"]
        landing = _landing_file(relative)
        documents.append({
            "id": doc_id,
            "title": title,
            "doc_type": "legal" if relative.parts[0] == "legal" else "news",
            "source": _nfc(path.name),
            "url": url,
            "landing_file": _nfc(landing.relative_to(PROJECT_ROOT).as_posix()) if landing else None,
            "landing_format": landing.suffix.lstrip(".").upper() if landing else None,
            "landing_bytes": landing.stat().st_size if landing else None,
            "markdown_chars": len(content),
            "markdown_bytes": path.stat().st_size,
            "chunks": counts.get(doc_id, 0),
            "modified": _iso(path.stat().st_mtime),
        })
    indexed_ids = {doc["id"] for doc in documents}
    total_chunks = sum(counts.values())
    return {
        "documents": documents,
        "total_chunks": total_chunks,
        "orphan_chunks": sum(count for doc_id, count in counts.items() if doc_id not in indexed_ids),
        "avg_chunk_chars": _avg_chunk_chars(),
    }


def _avg_chunk_chars() -> int:
    data = indexing.get_collection().get(include=["documents"])
    lengths = [len(text) for text in data["documents"] if text]
    return round(sum(lengths) / len(lengths)) if lengths else 0


@app.get("/api/documents/chunks")
def document_chunks(doc_id: str = Query(...)) -> dict:
    doc_id = _nfc(doc_id)
    data = indexing.get_collection().get(
        where={"source": doc_id.split("/")[-1]},
        include=["documents", "metadatas"],
    )
    chunks = [
        {"id": item_id, "content": content, "metadata": {**metadata, "url": metadata.get("url") or None}, "chars": len(content)}
        for item_id, content, metadata in zip(data["ids"], data["documents"], data["metadatas"])
        if _nfc(item_id).startswith(f"{doc_id}::")
    ]
    chunks.sort(key=lambda item: item["metadata"]["chunk_index"])
    return {"doc_id": doc_id, "chunks": chunks}


@app.get("/api/documents/markdown", response_class=PlainTextResponse)
def document_markdown(doc_id: str = Query(...)) -> str:
    path = (STANDARDIZED_DIR / _nfc(doc_id)).resolve()
    if STANDARDIZED_DIR.resolve() not in path.parents or not path.is_file():
        raise HTTPException(404, "Không tìm thấy tài liệu")
    return path.read_text(encoding="utf-8")


@app.post("/api/retrieve")
def retrieve_only(request: RetrieveRequest) -> dict:
    _require_index()
    threshold = SCORE_THRESHOLD if request.score_threshold is None else request.score_threshold
    try:
        trace = trace_retrieval(request.query, request.top_k, request.use_reranking, threshold)
    except Exception as exc:
        raise HTTPException(502, f"Retrieval lỗi: {type(exc).__name__}") from exc
    trace.pop("chunks")
    return trace


@app.post("/api/chat")
def chat(request: RetrieveRequest) -> dict:
    """Retrieve + generate giống generate_with_citation, kèm trace cho UI."""
    _require_index()
    started = time.perf_counter()
    threshold = SCORE_THRESHOLD if request.score_threshold is None else request.score_threshold
    provider, model = _model_label()
    error = None
    try:
        trace = trace_retrieval(request.query, request.top_k, request.use_reranking, threshold)
    except Exception as exc:
        raise HTTPException(502, f"Retrieval lỗi: {type(exc).__name__}") from exc

    chunks = trace.pop("chunks")
    ordered = reorder_for_llm(chunks)
    answer = ""
    if chunks:
        start = time.perf_counter()
        try:
            context = format_context(ordered)
            answer = call_llm(SYSTEM_PROMPT, f"Context:\n{context}\n\nQuestion: {request.query}").strip()
        except Exception as exc:
            error = type(exc).__name__
        trace["timings"]["llm_ms"] = round((time.perf_counter() - start) * 1000, 1)

    refused = not answer or _is_refusal(answer)
    if refused:
        answer = REFUSAL_MESSAGE
    answer = _display_answer(answer)
    cited = [] if refused else sorted({int(n) for n in re.findall(r"\[(\d+)\]", answer) if 1 <= int(n) <= len(ordered)})
    ranked_by_id = {source["id"]: source for source in trace["final"]}
    sources = [{**ranked_by_id[chunk["id"]], "rank": rank}
               for rank, chunk in enumerate(ordered, 1)]
    for source in sources:
        source["cited"] = source["rank"] in cited

    trace["timings"]["total_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return {
        **trace,
        "answer": answer,
        "refused": refused,
        "cited": cited,
        "sources": [] if refused else sources,
        "retrieval_source": "none" if refused else trace["retrieval_source"],
        "generator": f"{provider}/{model}",
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _read_json(path: Path):
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/evaluation")
def evaluation() -> dict:
    # Adapt main's saved evaluation to Thinh's UI without changing task11/data.
    artifact = "reports/demo_eval_results.json"
    saved = _read_json(PROJECT_ROOT / artifact)
    if not saved:
        artifact = "reports/gemini_eval_results.json"
        saved = _read_json(PROJECT_ROOT / artifact)
    golden = _read_json(EVAL_DIR / "golden_dataset.json") or []
    if saved:
        runs, configs = {}, {}
        for source_name, scores in saved["scores"].items():
            name = "A_dense" if source_name == "A_dense_only" else source_name
            rows = []
            for row in saved["cases"]:
                if row["config"] != source_name:
                    continue
                reference = next((case for case in golden if case["question"] == row["question"]), {})
                rows.append({
                    "question": row["question"], "answer": _display_answer(row["answer"]),
                    "refused": _is_refusal(row["answer"]),
                    "source_ids": row["retrieved_ids"],
                    "retrieval_method": "dense" if name == "A_dense" else "hybrid",
                    "expected_answer": reference.get("expected_answer", ""),
                    "expected_source": reference.get("source", ""),
                    "hit_expected_source": None, "latency_ms": row.get("latency_ms"), "retrieval_ms": None,
                    "faithfulness": row.get("faithfulness"),
                    "answer_relevancy": row.get("answer_relevance"),
                    "context_recall": row.get("context_recall"),
                    "context_precision": row.get("context_precision"),
                })
            runs[name] = rows
            latencies = [row["latency_ms"] for row in rows if row["latency_ms"] is not None]
            configs[name] = {
                "faithfulness": scores.get("faithfulness"),
                "answer_relevancy": scores.get("answer_relevance"),
                "context_recall": scores.get("context_recall"),
                "context_precision": scores.get("context_precision"),
                "average": scores.get("average"),
                "refusals": sum(row["refused"] for row in rows),
                "source_hit_rate": None,
                "latency_ms_mean": sum(latencies) / len(latencies) if latencies else None,
                "retrieval_ms_mean": None,
            }
        return {"summary": {
            "evaluation_date": saved["run_at_utc"][:10], "golden_size": saved["dataset_size"],
            "top_k": saved["top_k"], "generator": saved["generator_model"],
            "evaluator": saved["evaluator_model"], "evaluator_embedding": "",
            "method": saved.get("evaluation_method", "Gemini LLM judge"), "artifact": artifact,
            "configs": configs,
        }, "runs": runs, "golden": golden}
    summary = _read_json(EVAL_DIR / "results" / "summary.json")
    runs = {}
    for name in (summary or {}).get("configs", {}):
        rows = _read_json(EVAL_DIR / "results" / f"{name}.json") or []
        runs[name] = [{key: value for key, value in row.items() if key != "contexts"} for row in rows]
    return {
        "summary": summary,
        "runs": runs,
        "golden": _read_json(EVAL_DIR / "golden_dataset.json") or [],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("API_PORT", "8000")))
