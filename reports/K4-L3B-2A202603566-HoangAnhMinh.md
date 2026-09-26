# Báo Cáo Đóng Góp Cá Nhân (Individual Contribution Report)

> Báo cáo ghi nhận vai trò, ownership và bằng chứng kỹ thuật đóng góp trong sản phẩm nhóm.

---

## Thông tin

- **Họ và tên:** Hoàng Anh Minh
- **Mã học viên / MSSV:** 2A202603566
- **Nhóm:** Nhóm 3 (K4-L3B)
- **Vai trò đảm nhiệm:** Generation & UI (LLM Generation, Citation, Web Interface)
- **Repository / Branch:** `vvstdung89/K4-L3B-RAG-Pipeline` / `feature/generation-ui` (hoặc `main`)

---

## Phần việc đã thực hiện

| Module / Deliverable | Việc tôi trực tiếp làm | File / Commit / PR | Trạng thái |
|---|---|---|---|
| **Module Generation & Citation** | Xây dựng logic sinh câu trả lời có trích dẫn nguồn: hàm `reorder_for_llm` chống hiện tượng Lost-in-the-middle, hàm `format_context` định dạng chuẩn hóa kèm title và source, cơ chế gọi đa LLM provider (`call_llm`) và `generate_with_citation`. | `src/task10_generation.py` | **Done** |
| **Cơ chế Safe Refusal & Hallucination Guard** | Thiết lập prompt template nghiêm ngặt và cơ chế từ chối an toàn khi context rỗng hoặc model thiếu bằng chứng, tuân thủ đúng hợp đồng `GenerationResult`. | `src/task10_generation.py`, `src/contracts.py` | **Done** |
| **Giao diện Chatbot Streamlit** | Xây dựng và hoàn thiện ứng dụng web tương tác hỏi đáp RAG, hiển thị tin nhắn chat, số lượng chunks cấu hình (`top_k`), câu trả lời kèm bảng trích dẫn nguồn (sources, URL, method, score). | `app.py` | **Done** |
| **Tích hợp & Kiểm thử Hợp đồng** | Viết và chạy kiểm thử tự động đảm bảo `reorder_for_llm` không làm biến tính danh sách gốc, context chứa đúng source label, và validate kết quả generation. | `tests/test_contracts.py` | **Done** |

---

## Quyết định kỹ thuật quan trọng

1. **Quyết định 1: Áp dụng kỹ thuật sắp xếp lại ngữ cảnh (Context Reordering - U-shaped ordering)**  
   - **Lý do / Evidence:** Các mô hình ngôn ngữ lớn (LLM) thường gặp vấn đề "Lost in the Middle" (chú ý mạnh ở đầu và cuối prompt, lơ là các đoạn ở giữa). Thuật toán `reorder_for_llm` phân tách các chunk điểm cao nhất xếp vào đầu (`chunks[::2]`) và cuối (`chunks[1::2][::-1]`).  
   - **Trade-off:** Thứ tự ngữ cảnh không còn xếp tuần tự tuyệt đối theo rank điểm số từ trên xuống dưới, nhưng cải thiện đáng kể Context Recall và độ chính xác của câu trích dẫn từ LLM.

2. **Quyết định 2: Thực thi cơ chế Từ chối An toàn (Strict Safe Refusal) khi thiếu dữ liệu**  
   - **Lý do / Evidence:** Đối với dữ liệu chính sách pháp lý du lịch, thông tin sai lệch (hallucination) có thể gây hậu quả nghiêm trọng. Nếu retrieval không tìm thấy chunk liên quan hoặc confidence thấp, hệ thống trả về thông điệp chuẩn *"Tôi không thể xác minh thông tin này từ nguồn hiện có"* thay vì để LLM tự suy diễn.  
   - **Trade-off:** Chatbot sẽ không trả lời được các câu hỏi suy luận mở hoặc ngoài phạm vi kho dữ liệu, nhưng đảm bảo độ tin cậy và chỉ số Faithfulness đạt mức tối đa.

---

## Kiểm thử và kết quả

- **Test case đã thực hiện:**  
  - Chạy `pytest tests/test_contracts.py -k "test_reorder_is_non_mutating_and_context_contains_source"`: Kiểm tra tính bất biến của danh sách chunk và nhãn nguồn tài liệu.  
  - Chạy `pytest tests/test_contracts.py -k "test_generation_result_validator_accepts_safe_refusal"`: Kiểm tra chuẩn hóa `GenerationResult` và cơ chế từ chối an toàn.  
  - Toàn bộ suite `pytest`: 20/20 test cases PASS.
- **Kết quả trước/sau:**  
  - *Trước:* Giao diện chỉ có khung mẫu sơ khai; module generation thiếu xử lý trường hợp lỗi provider khiến pipeline bị gián đoạn.  
  - *Sau:* Pipeline sinh câu trả lời ổn định, trích dẫn rõ nguồn gốc tài liệu (Document title, source path) và giao diện Streamlit tương tác mượt mà.
- **Lỗi đã phát hiện và cách xử lý:**  
  - Lỗi thiếu dependency `python-dotenv` trong runtime gây `ModuleNotFoundError` khi load cấu hình provider. Đã bổ sung cài đặt và bọc try-except tại các điểm gọi LLM để tránh sập app khi mất kết nối mạng.

---

## Điều còn hạn chế

- **Hạn chế:** Hiện tại giao diện Streamlit chưa hỗ trợ cơ chế visual split-view (mở trực tiếp tài liệu gốc và tự động highlight dòng văn bản được trích dẫn cạnh câu trả lời).
- **Kế hoạch cải tiến:** Nếu có thêm thời gian, tôi sẽ triển khai streaming token theo thời gian thực và tích hợp bộ highlight văn bản trực quan (inline citation viewer) trên giao diện.

---

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích, trình diễn chạy thực tế trong buổi demo sản phẩm nhóm.

- **Ngày:** 25/09/2026  
- **Thành viên xác nhận:** Hoàng Anh Minh  
