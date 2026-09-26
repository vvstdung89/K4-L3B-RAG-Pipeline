"""
Task 8 — PageIndex vectorless fallback.

Hướng dẫn:
    1. Đọc PAGEINDEX_API_KEY từ .env.
    2. Upload tài liệu ở định dạng PageIndex hỗ trợ.
    3. Cache document IDs để không upload lại.
    4. Parse kết quả thành SearchResult có method pageindex.

PageIndex là dịch vụ ngoài: cần timeout và xử lý lỗi để pipeline không crash.
"""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "").strip()
STANDARDIZED_DIR = PROJECT_ROOT / "data" / "standardized"
LANDING_LEGAL_DIR = PROJECT_ROOT / "data" / "landing" / "legal"
DOC_ID_CACHE = PROJECT_ROOT / "data" / "pageindex_docs.json"
QUERY_TIMEOUT_SECONDS = 20


def is_configured() -> bool:
    return bool(PAGEINDEX_API_KEY)


def _client():
    if not is_configured():
        raise RuntimeError("PAGEINDEX_API_KEY chưa được cấu hình")
    from pageindex import PageIndexClient

    return PageIndexClient(api_key=PAGEINDEX_API_KEY)


def _load_cache() -> dict[str, str]:
    if DOC_ID_CACHE.exists():
        return json.loads(DOC_ID_CACHE.read_text(encoding="utf-8"))
    return {}


def upload_documents() -> None:
    """Upload PDF legal và lưu document IDs để tái sử dụng."""
    client = _client()
    cache = _load_cache()
    for path in sorted(LANDING_LEGAL_DIR.glob("*.pdf")):
        if path.name in cache:
            continue
        response = client.submit_document(str(path))
        doc_id = response.get("doc_id") or response.get("id")
        if not doc_id:
            raise RuntimeError(f"PageIndex không trả doc_id cho {path.name}: {response}")
        cache[path.name] = doc_id
        DOC_ID_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Uploaded {path.name} -> {doc_id}")


def _wait_for_retrieval(client, retrieval_id: str) -> dict:
    deadline = time.monotonic() + QUERY_TIMEOUT_SECONDS
    while True:
        response = client.get_retrieval(retrieval_id)
        if response.get("status") in {"completed", "failed"} or time.monotonic() > deadline:
            return response
        time.sleep(1)


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """Trả về pageindex SearchResult."""
    client = _client()
    cache = _load_cache()
    if not cache:
        raise RuntimeError("Chưa upload tài liệu lên PageIndex (python -m src.task8_pageindex_vectorless)")

    candidates = []
    for source, doc_id in cache.items():
        submitted = client.submit_query(doc_id, query)
        retrieval_id = submitted.get("retrieval_id") or submitted.get("id")
        response = _wait_for_retrieval(client, retrieval_id) if retrieval_id else submitted
        for node in response.get("retrieved_nodes", []) or []:
            text = "\n".join(
                part.get("relevant_content", "") if isinstance(part, dict) else str(part)
                for part in node.get("relevant_contents", [])
            ) or node.get("text", "")
            if text.strip():
                candidates.append((source, node, text.strip()))

    results = []
    # API không trả score: gán score giảm dần theo thứ tự PageIndex trả về.
    for rank, (source, node, text) in enumerate(candidates[:top_k]):
        node_id = node.get("node_id", rank)
        results.append({
            "id": f"pageindex::{source}::{node_id}",
            "content": text,
            "score": 1.0 - rank / max(len(candidates), 1),
            "metadata": {
                "source": source,
                "title": node.get("title") or Path(source).stem,
                "doc_type": "legal",
                "url": None,
                "chunk_index": rank,
            },
            "retrieval_method": "pageindex",
        })
    return results


if __name__ == "__main__":
    upload_documents()
