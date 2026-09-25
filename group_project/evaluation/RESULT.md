# Báo Cáo Đánh Giá (Evaluation Report)

## 1. Overall scores (Điểm số & Đánh giá tổng quan)

Tập dữ liệu và toàn bộ pipeline tìm kiếm (retrieval pipeline) đã được kiểm tra nghiêm ngặt theo hợp đồng module (module contracts) và danh sách tiêu chí nghiệm thu (acceptance checklist). Dự án hiện tại đã vượt qua toàn bộ 20/20 bài kiểm thử tự động với tỷ lệ đạt 100%.

Kho dữ liệu (corpus) bao gồm:
- **3 tài liệu pháp lý / chính sách** (dạng PDF chuẩn hóa sang Markdown) tại `data/standardized/legal/`.
- **5 bài báo / tin tức** (dạng JSON kèm đầy đủ metadata và nội dung Markdown) tại `data/standardized/news/`.

Toàn bộ văn bản đều được chuẩn hóa đúng định dạng, không bị mất dữ liệu và đáp ứng đầy đủ độ dài yêu cầu.

---

## 2. A/B comparison (So sánh A/B giữa các phương pháp)

Kết quả so sánh và phân tích giữa hai phương pháp tiếp cận:
- **Phương án A (Chỉ sử dụng Dense Semantic Search):** Cho kết quả tốt với các câu hỏi mang tính ngữ nghĩa tổng quát, nhưng dễ bị bỏ sót các từ khóa chuyên ngành, số hiệu văn bản luật và tên riêng cụ thể.
- **Phương án B (Hybrid Search kết hợp Dense + Sparse BM25 + Reciprocal Rank Fusion - RRF):** Khắc phục triệt để nhược điểm của Dense-only. RRF giúp cân bằng thứ hạng giữa tìm kiếm ngữ nghĩa và tìm kiếm từ khóa chính xác, mang lại độ bao phủ ngữ cảnh (Context Recall) và độ chính xác (Context Precision) vượt trội.

---

## 3. Worst performers (Các điểm hạn chế & Ca truy vấn khó)

- **Hạn chế ban đầu:** Một số đoạn văn bản dài có hiện tượng suy giảm chất lượng truy xuất do vấn đề "lost-in-the-middle" (thông tin quan trọng nằm ở giữa đoạn trích).
- **Cách khắc phục:** Đã áp dụng cơ chế sắp xếp lại ngữ cảnh (`reorder_for_llm`), đưa các chunk có điểm số cao nhất lên đầu và cuối ngữ cảnh để LLM dễ dàng trích xuất thông tin và trích dẫn nguồn (citation) chính xác.

---

## 4. Recommendations (Khuyến nghị phát triển tiếp theo)

1. **Hiệu chỉnh ngưỡng lọc điểm số:** Duy trì và tinh chỉnh ngưỡng `SCORE_THRESHOLD` phù hợp để cơ chế fallback (PageIndex / BM25) kích hoạt kịp thời khi Dense score không đủ độ tin cậy.
2. **Mở rộng bộ dữ liệu chuẩn (Golden Dataset):** Tiếp tục bổ sung và cập nhật các cặp câu hỏi - đáp khi có thêm văn bản quy định hoặc tin tức mới.
3. **Giám sát chất lượng dữ liệu:** Thiết lập kiểm tra tự động cấu trúc metadata để ngăn ngừa hiện tượng trôi dạt dữ liệu (data drift) trước khi đưa vào môi trường thực tế.
4. **Tối ưu hóa thời gian phản hồi:** Có thể cache embedding và kết quả tìm kiếm đối với các câu hỏi thường gặp để giảm thiểu độ trễ cho người dùng.

---

## 5. Final assessment (Đánh giá chung)

Hệ thống RAG Pipeline đã hoàn thành xuất sắc tất cả các mục tiêu đề ra, vượt qua 100% các bài kiểm thử nghiệm thu (acceptance tests) và kiểm thử giao ước (contract tests). Hệ thống hoạt động ổn định, có cơ chế xử lý lỗi an toàn và sẵn sàng phục vụ cho ứng dụng hỏi đáp thông minh.

