"""
Task 6 — Lexical search bằng BM25.

Dùng cùng corpus chunks với Task 5. BM25 phù hợp với từ khóa chính xác, mã tài
liệu và tên riêng. Output phải theo SearchResult và sort score giảm dần.
"""


from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata

from rank_bm25 import BM25L

from .contracts import validate_document, validate_search_results
from .task4_chunking_indexing import CHUNKS_PATH


# None loads Task 4's exported corpus. A list explicitly overrides it, e.g. in tests.
CORPUS: list[dict] | None = None
_TOKEN = re.compile(r"[^\W_]+(?:[/-][^\W_]+)*", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    """Keep Vietnamese accents and document codes such as 09/2017/QH14."""
    return _TOKEN.findall(unicodedata.normalize("NFC", text).casefold())


def _validate_corpus(corpus: list[dict]) -> None:
    seen = set()
    for item in corpus:
        validate_document(item, require_chunk=True)
        if item["id"] in seen:
            raise ValueError(f"Duplicate chunk ID in BM25 corpus: {item['id']}")
        seen.add(item["id"])


@lru_cache(maxsize=1)
def _read_corpus(path: str, modified_ns: int, size: int) -> list[dict]:
    # File identity is part of the cache key, so reindexing refreshes the corpus.
    corpus = []
    with Path(path).open(encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                validate_document(item, require_chunk=True)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid chunk at {path}:{line_number}: {exc}") from exc
            corpus.append(item)
    _validate_corpus(corpus)
    return corpus


def _get_corpus() -> list[dict]:
    if CORPUS is not None:
        return CORPUS
    path = CHUNKS_PATH.resolve()
    try:
        stat = path.stat()
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Missing chunk corpus: {path}. Run python -m src.task4_chunking_indexing first."
        ) from exc
    return _read_corpus(str(path), stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=2)
def _build_index(contents: tuple[str, ...]):
    tokenized = [_tokenize(content) for content in contents]
    if not any(tokenized):
        return None
    # BM25L has positive IDF even for one/two-document corpora; BM25Okapi's
    # signed IDF can otherwise score an exact match as zero.
    return BM25L(tokenized, k1=1.5, b=0.75, delta=0.5)


def build_bm25_index(corpus: list[dict]):
    """Tạo BM25 index từ cùng corpus chunks của Task 4."""
    _validate_corpus(corpus)
    return _build_index(tuple(item["content"] for item in corpus))


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """Trả về BM25 SearchResult theo score giảm dần."""
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    if not isinstance(top_k, int) or isinstance(top_k, bool):
        raise TypeError("top_k must be an integer")
    tokens = _tokenize(query)
    if not tokens or top_k <= 0:
        return []
    corpus = _get_corpus()
    bm25 = build_bm25_index(corpus)
    if bm25 is None:
        return []

    scores = bm25.get_scores(tokens)
    results = [
        {
            "id": item["id"],
            "content": item["content"],
            "score": float(score),
            "metadata": {**item["metadata"], "url": item["metadata"]["url"] or None},
            "retrieval_method": "bm25",
        }
        for item, score in zip(corpus, scores)
        if score > 0
    ]
    results.sort(key=lambda item: (-item["score"], item["id"]))
    results = results[:top_k]
    validate_search_results(results, top_k=top_k, expected_method="bm25")
    return results


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="BM25 search over the Task 4 chunk corpus")
    parser.add_argument("query", nargs="?", default="du lịch Việt Nam")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(lexical_search(args.query, args.top_k), ensure_ascii=False, indent=2))
