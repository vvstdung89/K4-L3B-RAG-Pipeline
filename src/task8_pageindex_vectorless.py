"""
Task 8 — PageIndex vectorless fallback.

Hướng dẫn:
    1. Đọc PAGEINDEX_API_KEY từ .env.
    2. Upload tài liệu ở định dạng PageIndex hỗ trợ.
    3. Cache document IDs để không upload lại.
    4. Parse kết quả thành SearchResult có method pageindex.

PageIndex là dịch vụ ngoài: cần timeout và xử lý lỗi để pipeline không crash.
"""

import os
import json
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
CACHE_PATH = Path(__file__).parent.parent / ".pageindex_documents.json"


def upload_documents() -> None:
    """Upload tài liệu và lưu document IDs để tái sử dụng."""
    """Upload supported source PDFs once; cache remote document IDs locally."""
    if not PAGEINDEX_API_KEY:
        return
    from pageindex import PageIndexClient
    client = PageIndexClient(index="cloud", api_key=PAGEINDEX_API_KEY)
    try:
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cache = {}
    landing = Path(__file__).parent.parent / "data" / "landing"
    changed = False
    for path in sorted(landing.rglob("*.pdf")) if landing.exists() else []:
        key = path.relative_to(landing).as_posix()
        if key in cache:
            continue
        response = client.submit_document(str(path), wait=True)
        doc_id = response.get("doc_id") if isinstance(response, dict) else None
        if doc_id:
            cache[key] = {"doc_id": doc_id, "source": path.name, "title": path.stem}
            changed = True
    if changed or not CACHE_PATH.exists():
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """Trả về pageindex SearchResult."""
    if top_k <= 0 or not query.strip() or not PAGEINDEX_API_KEY:
        return []
    try:
        if not CACHE_PATH.exists():
            upload_documents()
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        docs = list(cache.values())
        if not docs:
            return []
        from pageindex import PageIndexClient
        client = PageIndexClient(index="cloud", api_key=PAGEINDEX_API_KEY)
        answer = client.chat(query, doc_id=[item["doc_id"] for item in docs], citations=True)
        if isinstance(answer, dict):
            text = answer.get("answer") or answer.get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            text = str(answer)
        text = text.strip()
        if not text:
            return []
        source = docs[0]
        return [{"id": f"pageindex::{source['doc_id']}", "content": text, "score": 1.0,
                 "metadata": {"source": source["source"], "title": source["title"],
                              "doc_type": "legal", "url": None, "chunk_index": 0},
                 "retrieval_method": "pageindex"}]
    except Exception:
        # The retrieval pipeline will retain its hybrid results on provider errors.
        return []


if __name__ == "__main__":
    upload_documents()
