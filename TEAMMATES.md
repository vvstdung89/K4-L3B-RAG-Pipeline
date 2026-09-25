# Danh Sách Thành Viên & Phân Công Nhiệm Vụ (TEAMMATES)

**Dự án:** RAG Pipeline — K4 Day 8 Lab  
**Repository:** K4-L3B-RAG-Pipeline  

---

## 👥 Danh Sách Thành Viên

| STT | Họ và Tên | Mã Học Viên | Vai Trò Chính | Nhánh Phụ Trách (Git Branch) | Nhiệm Vụ Đảm Nhận |
| :---: | :--- | :---: | :--- | :--- | :--- |
| **1** | **Hoàng Anh Minh** *(Trưởng nhóm)* | `HV001` | **Evaluation & Integration** | `feature/evaluation-integration` | - Thiết lập kiến trúc, cấu hình môi trường chung, CI/CD và merge code.<br>- Xây dựng golden dataset (≥15 câu hỏi Q&A).<br>- Đo lường và đánh giá 4 metrics Ragas (Faithfulness, Answer Relevance, Context Recall, Context Precision).<br>- Phân tích so sánh A/B (Dense-only vs. Hybrid + RRF) và hoàn thiện `RESULT.md`. |
| **2** | **Nguyễn Văn A** | `HV002` | **Data Engineering** | `feature/data-pipeline` | - Thu thập dữ liệu: crawl ≥5 bài viết tin tức (`task2_crawl_news`) và thu thập ≥3 tài liệu pháp lý/chính sách PDF/DOCX (`task1_collect_legal_docs`).<br>- Chuyển đổi và chuẩn hóa tài liệu sang Markdown (`task3_convert_markdown`).<br>- Quản lý lưu trữ landing và processed data. |
| **3** | **Trần Thị B** | `HV003` | **Retrieval & Search** | `feature/retrieval-hybrid` | - Xây dựng module chunking và indexing với ChromaDB (`task4_chunking_indexing`).<br>- Triển khai Dense Semantic Search (`task5_semantic_search`) và BM25 Lexical Search (`task6_lexical_search`).<br>- Xây dựng thuật toán Reciprocal Rank Fusion (RRF) & cơ chế Fallback (`task7_reranking`, `task8_fallback`, `task9_retrieval_pipeline`).<br>- Hiệu chỉnh ngưỡng (calibration) `SCORE_THRESHOLD`. |
| **4** | **Lê Văn C** | `HV004` | **Generation & UI** | `feature/generation-ui` | - Xây dựng module tổng hợp câu trả lời có trích dẫn nguồn (citation) từ retrieved context (`task10_generation`).<br>- Hỗ trợ dynamic dispatch LLM provider (OpenAI / Gemini / Anthropic).<br>- Xây dựng và hoàn thiện giao diện Chatbot bằng Streamlit (`app.py`), hiển thị câu trả lời kèm citation, sources, retrieval method và điểm số. |

---

## 📌 Quy Trình Phối Hợp & Git Workflow

1. **Phân nhánh (Branching):**
   - Nhánh chính: `main` (chỉ merge khi code đã qua test).
   - Mỗi thành viên làm việc trên nhánh tính năng riêng (`feature/<ten-vai-tro>`).
2. **Quy tắc Commit & Code Quality:**
   - Commit message rõ ràng theo chuẩn Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`).
   - Tuân thủ [Module contracts](docs/MODULE_CONTRACTS.md). Đảm bảo chạy `pytest -q` đạt kết quả pass trước khi tạo Pull Request.
3. **Báo cáo cá nhân:**
   - Mỗi thành viên hoàn thành báo cáo cá nhân tại `reports/<ma-hoc-vien>-<ten>.md` theo mẫu chuẩn.
