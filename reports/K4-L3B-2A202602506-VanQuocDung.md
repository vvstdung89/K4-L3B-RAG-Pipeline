# Báo cáo đóng góp cá nhân

## Thông tin

- Họ và tên: Van Quoc Dung
- Mã học viên: 2A202602506
- Nhóm: K4-L3B
- Repository/branch: `vvstdung89/K4-L3B-RAG-Pipeline` / `vanquocdung-02505`
- Ngày cập nhật: 26/09/2026
- Phạm vi: sáu commit từ `e9e92be` đến `518d753`; nội dung và kết quả dưới đây được đối chiếu tại nhánh này.

## Phần việc đã thực hiện (nhóm làm chung data, phần task làm riêng trên branch, chọn 1 bài tốt merge trên main, demo có 1 bạn làm)


| Module/deliverable                    | Việc tôi trực tiếp làm                                                                                                                                                                           | File/commit                                                                                                                                                                                              | Trạng thái                                     |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| Task 3 — Chuẩn hóa Markdown           | Bổ sung chuẩn hóa Unicode NFC, làm sạch ký tự và nội dung điều hướng/quảng cáo; giữ cấu trúc đoạn, tiêu đề và metadata nguồn cho 3 tài liệu pháp lý, 5 bài viết.                                 | `src/task3_convert_markdown.py`, `data/standardized/`; [e9e92be](https://github.com/vvstdung89/K4-L3B-RAG-Pipeline/commit/e9e92be)                                                                       | Done                                           |
| Task 4 — Chunking và indexing         | Chia đoạn 500 ký tự, overlap 50; tạo ID ổn định, embedding theo batch, upsert Chroma theo cosine; kiểm tra cấu hình embedding và xuất corpus JSONL dùng chung.                                   | `src/task4_chunking_indexing.py`, `tests/test_indexing.py`; [885e4ab](https://github.com/vvstdung89/K4-L3B-RAG-Pipeline/commit/885e4ab)                                                                  | Done                                           |
| Task 5–6 — Dense và lexical search    | Dùng chung hàm embedding với indexing; đổi cosine distance thành similarity; triển khai BM25L, token hóa giữ dấu tiếng Việt và mã văn bản, cache index theo corpus.                              | `src/task5_semantic_search.py`, `src/task6_lexical_search.py`, `tests/test_search.py`; [ae16d13](https://github.com/vvstdung89/K4-L3B-RAG-Pipeline/commit/ae16d13)                                       | Done                                           |
| Task 7–9 — RRF, fallback và retrieval | Gộp thứ hạng theo ID một lần; quyết định fallback bằng cosine gốc; giữ kết quả cục bộ khi fallback lỗi. PageIndex lấy OCR của trang được dẫn nguồn, có timeout và cache theo tài liệu/tài khoản. | `src/task7_reranking.py`, `src/task8_pageindex_vectorless.py`, `src/task9_retrieval_pipeline.py`, `tests/test_retrieval.py`; [e26f128](https://github.com/vvstdung89/K4-L3B-RAG-Pipeline/commit/e26f128) | Done; PageIndex đã kiểm thử mock, chưa đo live |
| Task 10 — Generation có citation      | Sắp xếp context; hỗ trợ OpenAI/Gemini/Anthropic; yêu cầu JSON gồm claim và evidence, kiểm tra source ID và quote trước khi gắn citation; từ chối khi thiếu bằng chứng hoặc có lỗi.               | `src/task10_generation.py`, `tests/test_generation.py`; [53e9596](https://github.com/vvstdung89/K4-L3B-RAG-Pipeline/commit/53e9596)                                                                      | Done                                           |
| Golden dataset và A/B evaluation      | Xây dựng 15 câu hỏi phủ 8 tài liệu và 2 câu safety riêng; thêm trace retrieval/generation, chấm 4 metric RAGAS, lưu checkpoint và phân tích từng lỗi trong báo cáo.                              | `src/evaluation.py`, `src/task9_retrieval_pipeline.py`, `group_project/evaluation/`; [518d753](https://github.com/vvstdung89/K4-L3B-RAG-Pipeline/commit/518d753)                                         | Done                                           |


## Quyết định kỹ thuật quan trọng

1. **Thống nhất corpus và tách điểm fusion khỏi ngưỡng fallback.** Dense và BM25 dùng cùng chunk ID; RRF gộp theo thứ hạng với `k=60`, còn fallback dùng cosine gốc. Chế độ dense-only bỏ qua cả BM25 và RRF để so sánh A/B. **Trade-off:** RRF có thể đẩy chunk đúng ra khỏi top-k; ngưỡng cosine `0.5` vẫn cần hiệu chỉnh trên tập riêng.
2. **Kiểm tra evidence trước khi xuất câu trả lời.** Mỗi claim phải có source ID hợp lệ và quote tồn tại trong chunk sau chuẩn hóa Unicode/khoảng trắng; chỉ trả các nguồn thực sự được trích dẫn. **Trade-off:** Kiểm tra chặt có thể gây từ chối dù retrieval tìm đúng nguồn; quote khớp văn bản chưa chứng minh claim được hỗ trợ đầy đủ về ngữ nghĩa.

## Kiểm thử và kết quả

- Các test bổ sung kiểm tra ID/embedding, tìm kiếm tiếng Việt, RRF không sửa input, nhánh fallback/timeout, ánh xạ citation sau reorder và từ chối output sai schema/quote.
- Theo mục Verification trong [báo cáo evaluation của nhánh](https://github.com/vvstdung89/K4-L3B-RAG-Pipeline/blob/518d753/group_project/evaluation/RESULT.md): `pytest tests/test_contracts.py -q` đạt 15 passed; `pytest tests/test_acceptance.py -q` đạt 5 passed; `pytest -q` đạt 138 passed. Đây là kết quả đã ghi nhận; lần cập nhật báo cáo này không chạy lại test hoặc gọi API evaluation.
- Run ngày 25/09/2026 trong [results.json](https://github.com/vvstdung89/K4-L3B-RAG-Pipeline/blob/518d753/group_project/evaluation/results.json) hoàn tất 30 lượt golden và 4 lượt safety; dùng `gpt-4.1-mini` cho generation/judge, `text-embedding-3-small` cho embedding, RAGAS 0.4.3 và `top_k=5`.


| Cấu hình         | Faithfulness | Answer relevance | Context recall | Context precision |
| ---------------- | ------------: | ----------------: | --------------: | -----------------: |
| A — Dense-only   | 1.000        | 0.562            | 0.967          | 0.845             |
| B — Hybrid + RRF | 1.000        | 0.660            | 0.900          | 0.745             |


- Số lượt có điểm theo thứ tự bốn metric: A = 12/14/15/15, B = 14/15/15/14, trên 15 câu mỗi cấu hình. Giá trị thiếu giữ `null`, không tính là 0; faithfulness 1.000 chỉ áp dụng cho các câu có điểm.
- Hybrid tăng relevance 0.097 theo số chưa làm tròn, nhưng giảm recall 0.067 và precision 0.100; tỷ lệ tìm đúng chunk kỳ vọng giảm từ 14/15 xuống 12/15. Chưa đủ bằng chứng kết luận hybrid tốt hơn tổng thể.
- Safety đạt 2/2 ở mỗi cấu hình. Riêng golden có 3 lỗi generation ở A và 1 ở B dẫn đến từ chối, cùng 1 lỗi metric mỗi cấu hình. Phân tích Q05 cho thấy RRF làm mất chunk định nghĩa; Q09/Q12/Q14 có lỗi generation dù đã tìm đúng chunk. Các lỗi này được ghi nhận để xử lý tiếp.

## Điều còn hạn chế

- PageIndex chưa được cấu hình trong run A/B nên chưa có kết quả fallback thực tế. Benchmark nhỏ, mỗi câu chạy một lần; generator và judge cùng model nên có thể có thiên lệch.
- Corpus còn tài liệu visa lưu trữ và bài `article_01` không khớp tiêu đề crawl với nội dung; cần rà soát nguồn trước khi mở rộng dữ liệu.
- Ưu tiên tiếp theo: lưu thông báo lỗi `ValueError` đã loại thông tin nhạy cảm để phân biệt lỗi schema/quote/provider, chạy lại các ca generation lỗi và hai metric bị thiếu; sau đó hiệu chỉnh chunking/RRF trên tập kiểm thử riêng.

## Xác nhận đóng góp

Nội dung trên ghi nhận phần việc có thể đối chiếu bằng sáu commit, mã nguồn, test và kết quả evaluation trên nhánh `vanquocdung-02505`.

- Thành viên: Van Quoc Dung — 2A202602506
- Ngày lập báo cáo: 26/09/2026

