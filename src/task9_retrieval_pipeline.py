"""
Task 9 — Retrieval pipeline hoàn chỉnh.

Luồng xử lý:
    1. Chạy semantic_search và lexical_search.
    2. Fuse hai danh sách bằng RRF đúng một lần.
    3. Lấy best cosine score gốc từ dense results.
    4. Nếu score dưới threshold, thử PageIndex fallback.
    5. Nếu fallback lỗi, trả hybrid results thay vì crash.

Không so sánh threshold với RRF score vì hai thang đo khác nhau.
"""

import os

from dotenv import load_dotenv

from .task5_semantic_search import semantic_search
from .task6_lexical_search import lexical_search
from .task7_reranking import rerank_rrf
from .task8_pageindex_vectorless import pageindex_search


load_dotenv()

# Hiệu chỉnh bằng query trong/ngoài domain (xem GET /api/calibration).
SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD") or 0.3)
DEFAULT_TOP_K = 5
CANDIDATE_MULTIPLIER = 2


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    use_reranking: bool = True,
) -> list[dict]:
    """Trả về hybrid (hoặc dense khi tắt RRF) hoặc pageindex SearchResult."""
    dense = semantic_search(query, top_k=top_k * CANDIDATE_MULTIPLIER)
    if use_reranking:
        sparse = lexical_search(query, top_k=top_k * CANDIDATE_MULTIPLIER)
        ranked = rerank_rrf([dense, sparse], top_k=top_k)
    else:
        ranked = dense[:top_k]

    best_dense_score = dense[0]["score"] if dense else 0.0
    if best_dense_score < score_threshold:
        try:
            fallback = pageindex_search(query, top_k=top_k)
            if fallback:
                return fallback[:top_k]
        except Exception:
            pass
    return ranked[:top_k]


if __name__ == "__main__":
    for result in retrieve("Điều kiện cấp thẻ hướng dẫn viên du lịch quốc tế", top_k=3):
        print(result["retrieval_method"], round(result["score"], 4), result["id"])
