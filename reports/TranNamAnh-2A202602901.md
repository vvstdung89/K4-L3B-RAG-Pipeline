# Báo cáo đóng góp cá nhân

## Thông tin

- Họ và tên: Trần Nam Anh  
- Mã học viên: 2A202602901
- Nhóm: K4-L3B
- Repository/branch: K4-L3B-RAG-Pipeline / branch hiện tại
- Ngày ghi nhận: 2026-09-25

## Phần việc đã thực hiện

| Module/deliverable | Việc thực hiện | Bằng chứng | Trạng thái |
|---|---|---|---|
| Task 1 — Thu thập tài liệu pháp lý | Hoàn thiện bước thu thập tài liệu chính sách/quy định phục vụ corpus RAG. | `src/task1_collect_legal_docs.py`; `data/landing/legal/` | Done |
| Task 2 — Crawl bài viết/tin tức | Hoàn thiện bước crawl bài viết và thông báo, lưu dữ liệu đầu vào theo cấu trúc pipeline. | `src/task2_crawl_news.py`; `data/landing/news/` | Done |
| Task 3 — Chuẩn hóa Markdown | Hoàn thiện chuyển đổi, làm sạch và chuẩn hóa dữ liệu đầu vào sang Markdown. | `src/task3_convert_markdown.py`; `data/processed/` | Done |
| Task 4 — Chunking, embedding và indexing | Hoàn thiện chia tài liệu thành chunks, tạo embeddings và lập chỉ mục để truy xuất. | `src/task4_chunking_indexing.py` | Done |
| Task 5 — Semantic search | Hoàn thiện truy xuất ngữ nghĩa bằng ChromaDB, dùng chung hàm embedding với Task 4. | `src/task5_semantic_search.py` | Done |
| Task 6 — Lexical search | Hoàn thiện truy xuất từ khóa bằng BM25 trên cùng corpus chunks. | `src/task6_lexical_search.py` | Done |
| Task 7 — Kết hợp kết quả retrieval | Hoàn thiện Reciprocal Rank Fusion (RRF) để gộp kết quả dense và BM25 theo ID. | `src/task7_reranking.py` | Done |
| Task 8 — PageIndex fallback | Hoàn thiện fallback PageIndex vectorless để truy xuất khi cần phương án dự phòng. | `src/task8_pageindex_vectorless.py` | Done |
| Golden dataset | Tạo lại 15 câu hỏi và đáp án từ corpus chuẩn hóa; mỗi `expected_context` được đối chiếu với văn bản nguồn sau khi chuẩn hóa khoảng trắng. | `group_project/evaluation/golden_dataset.json` | Done |
| A/B evaluation và báo cáo | Cấu hình Gemini embedding/generation/evaluator; build index 540 chunks theo quota free-tier; chạy đủ 15 golden cases trên hai cấu hình và ghi kết quả. | `src/task11_evaluation.py`; `reports/gemini_eval_results.json`; `reports/RESULT.md` | Done |

## Quyết định kỹ thuật

1. **Chỉ dùng bằng chứng có trong corpus chuẩn hóa.** Câu hỏi bao gồm luật, visa và bài viết du lịch để tạo các truy vấn từ khóa, ngữ nghĩa và dễ nhầm nguồn. Context trích từ tài liệu tương ứng; kiểm tra lại bằng so khớp sau khi chuẩn hóa khoảng trắng.
   **Trade-off:** Một số context dài hơn một câu để giữ đủ điều kiện và ngữ cảnh phân biệt nguồn.

2. **Giới hạn tốc độ theo free-tier và lưu checkpoint.** Embedding chạy batch 100 chunks với một phút giữa các batch; A/B lưu từng lượt để có thể tiếp tục sau lỗi quota. PageIndex fallback tắt cho cả hai arm để cô lập dense-only và hybrid + RRF.
   **Trade-off:** Indexing/evaluation chạy chậm hơn; embedding quota trả 429 giữa chừng nhưng checkpoint cho phép hoàn tất mà không embed lại phần đã lưu.

## Kiểm thử và kết quả

- `python -m pytest -q`: 20 passed sau khi bảo toàn signatures theo contract.
- Index 540 chunks bằng `gemini-embedding-001`; chạy đủ 30 lượt cấu hình/case (15 câu × 2) với `gemini-3.5-flash-lite` làm generator và evaluator.
- Dense-only đạt average 0.827; hybrid + RRF đạt 0.744. Delta B−A lần lượt: faithfulness -0.033, answer relevance -0.095, context recall -0.067, context precision -0.137.

## Hạn chế

- Latency từng request và mức phí không được ghi trong run; quota free-tier đã giới hạn tốc độ embedding.
- Metric được chấm bởi cùng model Gemini làm LLM judge; cần đọc case outputs và xác minh các lỗi quan trọng thủ công.
- Môi trường dùng Python 3.14.7, trong khi `pyproject.toml` khai báo hỗ trợ Python dưới 3.14.

## Xác nhận đóng góp

Báo cáo ghi nhận các thay đổi và kết quả có bằng chứng trong repository; người nộp chịu trách nhiệm xác nhận thông tin cá nhân và nội dung đóng góp trước khi nộp.
