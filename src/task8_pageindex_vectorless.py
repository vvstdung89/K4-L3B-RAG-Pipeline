"""Task 8: PageIndex vectorless retrieval with original page evidence.

API contract: https://docs.pageindex.ai/api-reference (2026-09-25).
Use documented chat citations to locate pages, then fetch original OCR text.
The generated chat answer is never returned as source evidence. Requests have
explicit timeouts; the older installed SDK does not expose request timeouts.
"""

import hashlib
import json
import logging
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import quote

from dotenv import load_dotenv
import requests

from .contracts import validate_search_results
from .task4_chunking_indexing import load_documents


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "").strip()
CACHE_PATH = ROOT / "pageindex_doc_ids.json"
PDF_DIR = ROOT / "pageindex_pdfs"
API_URL = "https://api.pageindex.ai"
REQUEST_TIMEOUT = 30.0
SEARCH_BUDGET = 60.0
PROCESSING_TIMEOUT = 120.0
logger = logging.getLogger(__name__)


def _request(method: str, path: str, *, deadline: float, **kwargs) -> dict:
    if not PAGEINDEX_API_KEY:
        raise RuntimeError("Set PAGEINDEX_API_KEY in .env to enable PageIndex")
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("PageIndex time budget exhausted")
    response = requests.request(
        method, API_URL + path, headers={"api_key": PAGEINDEX_API_KEY},
        timeout=min(REQUEST_TIMEOUT, remaining), **kwargs,
    )
    if not response.ok:
        # Provider bodies may contain sensitive data. Expose only the status.
        raise RuntimeError(f"PageIndex HTTP {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("PageIndex response must be an object")
    return payload


def _account() -> str:
    return hashlib.sha256(PAGEINDEX_API_KEY.encode()).hexdigest()


def _fingerprint(document: dict) -> str:
    data = json.dumps(document, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _read_cache() -> dict:
    if not CACHE_PATH.exists():
        return {"version": 1, "account": _account(), "documents": {}}
    data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("version") != 1
            or not isinstance(data.get("documents"), dict)):
        raise ValueError("Invalid PageIndex cache; move it aside and upload again")
    if data.get("account") != _account():
        raise ValueError("PageIndex cache belongs to another API key")
    for entry in data["documents"].values():
        if (not isinstance(entry, dict) or any(
            not isinstance(entry.get(key), str) or not entry[key]
            for key in ("doc_id", "fingerprint", "filename")
        )):
            raise ValueError("Invalid PageIndex cache entry")
    return data


def _write_cache(data: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=CACHE_PATH.parent,
        suffix=".tmp", delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(data, handle, ensure_ascii=False, indent=2)
    try:
        temporary.replace(CACHE_PATH)
    finally:
        temporary.unlink(missing_ok=True)


def _to_pdf(document: dict, path: Path) -> None:
    """Render normalized text with an embedded font supporting Vietnamese."""
    from fpdf import FPDF

    candidates = [
        os.getenv("PAGEINDEX_FONT_PATH", ""),
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    font = next((Path(name) for name in candidates if name and Path(name).is_file()), None)
    if font is None:
        raise RuntimeError("Set PAGEINDEX_FONT_PATH to a Unicode TrueType font")
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)
    pdf.add_font("Source", fname=str(font))
    pdf.add_page()
    pdf.set_title(document["metadata"]["title"])
    for line in document["content"].splitlines():
        heading = re.match(r"^(#{1,6})\s+(.+)", line)
        pdf.set_font("Source", size=14 if heading else 10)
        # Word/PDF extraction often maps the Symbol bullet into private-use U+F0B7.
        text = (heading.group(2) if heading else line).replace("\uf0b7", "•")
        pdf.multi_cell(w=0, h=6, text=text.replace("\t", "    "),
                       new_x="LMARGIN", new_y="NEXT")
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))


def _tree_status(doc_id: str, deadline: float) -> str:
    response = _request("GET", f"/doc/{quote(doc_id, safe='')}/",
                        deadline=deadline, params={"type": "tree"})
    status = response.get("status")
    if status not in {"queued", "processing", "completed", "failed", "error"}:
        raise ValueError("Invalid PageIndex processing status")
    return status


def upload_documents() -> None:
    """Upload changed standardized documents; persist each ID before polling.

    Rerunning resumes queued work and reuses unchanged IDs. Remote documents are
    never deleted automatically. Each document has a bounded processing wait.
    """
    if not PAGEINDEX_API_KEY:
        raise RuntimeError("Set PAGEINDEX_API_KEY in .env before uploading")
    documents = load_documents()
    if not documents:
        raise ValueError("No standardized documents to upload")
    cache = _read_cache()
    for document in documents:
        fingerprint = _fingerprint(document)
        entry = cache["documents"].get(document["id"])
        if not entry or entry["fingerprint"] != fingerprint or entry.get("status") == "failed":
            filename = f"{fingerprint}.pdf"
            path = PDF_DIR / filename
            _to_pdf(document, path)
            with path.open("rb") as handle:
                response = _request(
                    "POST", "/doc/", deadline=time.monotonic() + REQUEST_TIMEOUT,
                    files={"file": (filename, handle, "application/pdf")},
                )
            doc_id = response.get("doc_id")
            if not isinstance(doc_id, str) or not doc_id.strip():
                raise ValueError("PageIndex upload returned no doc_id")
            entry = {"doc_id": doc_id, "fingerprint": fingerprint,
                     "filename": filename, "status": "processing"}
            cache["documents"][document["id"]] = entry
            _write_cache(cache)
        if entry.get("status") == "completed":
            continue
        deadline = time.monotonic() + PROCESSING_TIMEOUT
        while True:
            status = _tree_status(entry["doc_id"], deadline)
            entry["status"] = "failed" if status == "error" else status
            _write_cache(cache)
            if status == "completed":
                break
            if status in {"failed", "error"}:
                raise RuntimeError("PageIndex document processing failed; rerun upload to retry")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("PageIndex processing pending; rerun upload to resume")
            time.sleep(min(1.0, remaining))
    # Removed sources must not participate in future searches.
    active = {document["id"] for document in documents}
    cache["documents"] = {key: value for key, value in cache["documents"].items() if key in active}
    _write_cache(cache)


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """Locate cited pages with PageIndex and return source OCR, scored by rank."""
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    if isinstance(top_k, bool) or not isinstance(top_k, int):
        raise TypeError("top_k must be an integer")
    if not query.strip() or top_k <= 0:
        return []
    if not PAGEINDEX_API_KEY:
        raise RuntimeError("Set PAGEINDEX_API_KEY in .env to enable PageIndex")
    deadline = time.monotonic() + SEARCH_BUDGET
    cache = _read_cache()
    sources = {}
    for document in load_documents():
        entry = cache["documents"].get(document["id"])
        if not entry or entry["fingerprint"] != _fingerprint(document):
            continue  # Do not serve stale or removed sources.
        if entry.get("status") != "completed":
            if _tree_status(entry["doc_id"], deadline) != "completed":
                continue
        sources[entry["filename"]] = (entry, document)
    if not sources:
        raise RuntimeError("No current PageIndex documents ready; run upload_documents first")
    response = _request("POST", "/chat/completions", deadline=deadline, json={
        "doc_id": [entry["doc_id"] for entry, _ in sources.values()],
        "messages": [{"role": "user", "content": (
            "Find the source passages relevant to the following question. "
            "Cite each relevant page using inline document citations. "
            "If no source supports it, return no citations. Question: " + query.strip()
        )}],
        "stream": False, "temperature": 0, "enable_citations": True,
    })
    content = response["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise ValueError("Invalid PageIndex chat response")
    # Official inline format: <doc=file.pdf;page=1;block=p1_text_3>.
    citations = re.findall(r"<doc=([^;<>]+);page=(\d+)(?:;block=[^<>]+)?>", content)
    results, seen, pages_by_doc = [], set(), {}
    for filename, page_string in citations:
        if filename not in sources:
            continue
        entry, document = sources[filename]
        doc_id, page = entry["doc_id"], int(page_string)
        if page < 1 or (doc_id, page) in seen:
            continue
        seen.add((doc_id, page))
        if doc_id not in pages_by_doc:
            try:
                ocr = _request("GET", f"/doc/{quote(doc_id, safe='')}/", deadline=deadline,
                               params={"type": "ocr", "format": "page"})
                if ocr.get("status") != "completed" or not isinstance(ocr.get("result"), list):
                    continue
                pages_by_doc[doc_id] = {
                    item["page_index"]: item["markdown"] for item in ocr["result"]
                    if isinstance(item, dict) and type(item.get("page_index")) is int
                    and isinstance(item.get("markdown"), str)
                }
            except (requests.RequestException, TimeoutError, RuntimeError, ValueError) as exc:
                logger.warning("PageIndex OCR unavailable (%s)", type(exc).__name__)
                pages_by_doc[doc_id] = {}
                continue
        text = pages_by_doc[doc_id].get(page, "").strip()
        if not text:
            continue
        results.append({
            "id": f"pageindex::{doc_id}::page-{page}", "content": text,
            "score": 1.0 / (len(results) + 1), "retrieval_method": "pageindex",
            "metadata": {**document["metadata"], "chunk_index": page - 1,
                         "page": page, "pageindex_doc_id": doc_id},
        })
        if len(results) == top_k:
            break
    validate_search_results(results, top_k=top_k, expected_method="pageindex")
    return results


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", help="Omit to upload/resume documents")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    if args.query is None:
        upload_documents()
        print("PageIndex documents ready.")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(pageindex_search(args.query, args.top_k), ensure_ascii=False, indent=2))
