"""
Task 6 — Lexical search bằng BM25.

Dùng cùng corpus chunks với Task 5. BM25 phù hợp với từ khóa chính xác, mã tài
liệu và tên riêng. Output phải theo SearchResult và sort score giảm dần.
"""


CORPUS: list[dict] = []
_INDEX = None


def build_bm25_index(corpus: list[dict]):
    """Tạo BM25 index từ cùng corpus chunks của Task 4."""
    import re
    tokenized = [re.findall(r"\w+", item["content"].casefold(), flags=re.UNICODE) for item in corpus]
    try:
        from rank_bm25 import BM25Okapi
        return BM25Okapi(tokenized)
    except ImportError:
        # Small dependency-free BM25 fallback (Okapi, k1=1.5, b=0.75).
        from collections import Counter
        import math
        class SimpleBM25:
            def __init__(self, docs):
                self.docs = docs
                self.lengths = [len(doc) for doc in docs]
                self.avgdl = sum(self.lengths) / max(len(docs), 1)
                self.tf = [Counter(doc) for doc in docs]
                df = Counter(term for counts in self.tf for term in counts)
                self.idf = {term: math.log(1 + (len(docs) - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()}
            def get_scores(self, query):
                scores = []
                for counts, length in zip(self.tf, self.lengths):
                    score = 0.0
                    for term in query:
                        frequency = counts.get(term, 0)
                        if frequency:
                            score += self.idf.get(term, 0.0) * frequency * 2.5 / (frequency + 1.5 * (1 - 0.75 + 0.75 * length / max(self.avgdl, 1)))
                    scores.append(score)
                return scores
        return SimpleBM25(tokenized)


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """Trả về BM25 SearchResult theo score giảm dần."""
    global CORPUS, _INDEX
    if top_k <= 0 or not query.strip():
        return []
    if not CORPUS:
        from .task4_chunking_indexing import chunk_documents, load_documents
        CORPUS = chunk_documents(load_documents())
        _INDEX = None
    if not CORPUS:
        return []
    import re
    tokens = re.findall(r"\w+", query.casefold(), flags=re.UNICODE)
    if not tokens:
        return []
    if _INDEX is None:
        _INDEX = build_bm25_index(CORPUS)
    scores = _INDEX.get_scores(tokens)
    order = sorted(range(len(CORPUS)), key=lambda i: (-float(scores[i]), CORPUS[i]["id"]))
    results, seen = [], set()
    for i in order:
        item = CORPUS[i]
        score = float(scores[i])
        if score <= 0 or item["id"] in seen:
            continue
        seen.add(item["id"])
        results.append({"id": item["id"], "content": item["content"], "score": score,
                        "metadata": item["metadata"], "retrieval_method": "bm25"})
        if len(results) >= top_k:
            break
    return results


if __name__ == "__main__":
    for result in lexical_search("test query", top_k=3):
        print(result)
