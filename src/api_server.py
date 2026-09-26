"""
Backend FastAPI cho UI React (src/src). Mọi dữ liệu lấy từ data/, ChromaDB và
group_project/evaluation/results — không có dữ liệu mẫu.

Chạy:
    python -m src.api_server            # http://127.0.0.1:8000
    cd src && npm run dev               # Vite proxy /api sang cổng 8000
"""

import json
import os
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
from .task5_semantic_search import restore_metadata, semantic_search  # noqa: E402
from .task6_lexical_search import lexical_search  # noqa: E402
from .task7_reranking import rerank_rrf  # noqa: E402
from .task9_retrieval_pipeline import CANDIDATE_MULTIPLIER, SCORE_THRESHOLD  # noqa: E402
from .task10_generation import (  # noqa: E402
    REFUSAL_MESSAGE,
    SYSTEM_PROMPT,
    TEMPERATURE,
    TOP_K,
    TOP_P,
    build_user_message,
    call_llm,
    cited_numbers,
    is_refusal,
    resolve_model,
)


LANDING_DIR = PROJECT_ROOT / "data" / "landing"
STANDARDIZED_DIR = indexing.STANDARDIZED_DIR
EVAL_DIR = PROJECT_ROOT / "group_project" / "evaluation"
RRF_K = 60

app = FastAPI(title="Du Lịch Việt RAG API")


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

    sparse: list[dict] = []
    if use_reranking:
        start = time.perf_counter()
        sparse = lexical_search(query, top_k=candidates)
        timings["bm25_ms"] = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        ranked = rerank_rrf([dense, sparse], top_k=top_k, k=RRF_K)
        timings["rrf_ms"] = (time.perf_counter() - start) * 1000
    else:
        ranked = dense[:top_k]

    best_dense_score = dense[0]["score"] if dense else 0.0
    fallback = {"triggered": best_dense_score < score_threshold, "configured": pageindex.is_configured(),
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
            fallback["error"] = str(error)
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
    query: str = Field(min_length=1)
    top_k: int = Field(default=TOP_K, ge=1, le=20)
    use_reranking: bool = True
    score_threshold: float | None = None


@app.get("/api/config")
def get_config() -> dict:
    provider, model = resolve_model()
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
        "embedding_provider": indexing.EMBEDDING_PROVIDER,
        "embedding_model": indexing.EMBEDDING_MODEL,
        "embedding_dim": indexing.EMBEDDING_DIM,
        "chunk_size": indexing.CHUNK_SIZE,
        "chunk_overlap": indexing.CHUNK_OVERLAP,
        "chunking_method": indexing.CHUNKING_METHOD,
        "collection_name": indexing.COLLECTION_NAME,
        "collection_count": collection.count(),
        "distance": (collection.metadata or {}).get("hnsw:space", "cosine"),
        "pageindex_configured": pageindex.is_configured(),
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
    for path in sorted(STANDARDIZED_DIR.rglob("*.md")):
        relative = path.relative_to(STANDARDIZED_DIR)
        doc_id = _nfc(relative.as_posix())
        title, url, content = indexing._parse_markdown(path)
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
        {"id": item_id, "content": content, "metadata": restore_metadata(metadata), "chars": len(content)}
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
    threshold = SCORE_THRESHOLD if request.score_threshold is None else request.score_threshold
    trace = trace_retrieval(request.query, request.top_k, request.use_reranking, threshold)
    trace.pop("chunks")
    return trace


@app.post("/api/chat")
def chat(request: RetrieveRequest) -> dict:
    """Retrieve + generate giống generate_with_citation, kèm trace cho UI."""
    started = time.perf_counter()
    threshold = SCORE_THRESHOLD if request.score_threshold is None else request.score_threshold
    provider, model = resolve_model()
    error = None
    try:
        trace = trace_retrieval(request.query, request.top_k, request.use_reranking, threshold)
    except Exception as exc:
        raise HTTPException(502, f"Retrieval lỗi: {exc}") from exc

    chunks = trace.pop("chunks")
    answer = ""
    if chunks:
        start = time.perf_counter()
        try:
            answer = call_llm(SYSTEM_PROMPT, build_user_message(request.query, chunks)).strip()
        except Exception as exc:
            error = str(exc)
        trace["timings"]["llm_ms"] = round((time.perf_counter() - start) * 1000, 1)

    refused = not answer or is_refusal(answer)
    if refused:
        answer = REFUSAL_MESSAGE
    cited = [] if refused else cited_numbers(answer, len(chunks))
    for source in trace["final"]:
        source["cited"] = source["rank"] in cited

    trace["timings"]["total_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return {
        **trace,
        "answer": answer,
        "refused": refused,
        "cited": cited,
        "sources": [] if refused else trace["final"],
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
