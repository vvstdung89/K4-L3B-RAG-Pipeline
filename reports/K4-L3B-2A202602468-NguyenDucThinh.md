# Individual contribution report

---

## Thông tin

- Họ và tên: Nguyễn Đức Thịnh
- Mã học viên: 2A202602468
- Nhóm: Nhóm 3 (K4-L3B)
- Repository/branch: https://github.com/vvstdung89/K4-L3B-RAG-Pipeline/tree/Thihn/02468

## Phần việc đã thực hiện

| Module/deliverable | Việc tôi trực tiếp làm | File/commit/PR | Trạng thái |
|---|---|---|---|
| Task 3 – chuyển tài liệu sang Markdown | Chuyển PDF luật/visa và bài news JSON sang `.md`, lọc bớt rác (menu, link, ảnh) trong bài báo | `src/task3_convert_markdown.py`, commit `9d1199e` | Done |
| UI tra cứu tài liệu (React) | Dựng khung giao diện 6 tab: Trò chuyện, Pipeline, Xếp hạng, Đánh giá A/B, Kho dữ liệu, Cấu hình | `src/src/`, commit `96a0a13` | Done |
| Backend cho UI | Viết API FastAPI để UI lấy dữ liệu thật thay vì dữ liệu mẫu | `src/api_server.py` | Done |
| Nối UI với dữ liệu thật | Viết lại các view để gọi API: danh sách tài liệu, chunk, hỏi đáp có trích dẫn, trace pipeline, so sánh xếp hạng, kết quả A/B | `src/src/api.ts`, `src/src/views/*.tsx`, `src/src/components/ui.tsx` | Done |

## Quyết định kỹ thuật quan trọng

1. **Quyết định:** Cho UI đọc dữ liệu qua một backend nhỏ (FastAPI), và backend này gọi lại đúng các hàm task4–task10 nhóm đã viết.  
   **Lý do/evidence:** Bản UI đầu tiên toàn dữ liệu giả (chính sách hãng bay, 284 chunks bịa…), nhìn đẹp nhưng không khớp gì với `data/`. Giờ tab Kho dữ liệu hiện đúng 8 tài liệu, 551 chunks trong ChromaDB. Tab Trò chuyện thì trả lời bằng chính pipeline hybrid + RRF của nhóm.  
   **Trade-off:** Muốn xem UI thì phải chạy thêm một tiến trình (`python -m src.api_server`). Hàm `trace_retrieval` cũng lặp lại một phần logic của `retrieve()` để lấy được thời gian từng bước.

2. **Quyết định:** Bỏ hết các nút "làm màu" mà pipeline thật không có (OCR, upload file, crawl URL, HyDE, cross-encoder reranker, memory). Tab Cấu hình chỉ cho xem, không cho sửa.  
   **Lý do/evidence:** Mấy nút đó bấm vào chỉ hiện `alert()`, lúc demo dễ bị hỏi mà không trả lời được. Cấu hình thật thì nằm ở `.env`.  
   **Trade-off:** UI trông "ít tính năng" hơn bản mockup, nhưng cái gì hiện lên cũng chạy thật.

## Kiểm thử và kết quả

- Test hoặc query tôi đã dùng: gọi thử từng endpoint (`/api/config`, `/api/documents`, `/api/documents/chunks`, `/api/evaluation`, `/api/retrieve`, `/api/chat`), cả trực tiếp lẫn qua proxy của Vite. Chạy `npx tsc --noEmit` để check TypeScript. Query mẫu: "Công dân Nhật Bản được miễn visa vào Việt Nam bao nhiêu ngày?", "Điều kiện cấp thẻ hướng dẫn viên du lịch quốc tế là gì?".
- Kết quả trước/sau nếu có: trước thì mọi tab là dữ liệu mẫu. Sau khi sửa, câu hỏi visa trả lời có trích dẫn [1], nguồn đúng file `exotravel_vietnam_visa_information`, mất khoảng 2,3 s (dense ~0,5 s, LLM ~1,8 s). TypeScript không còn lỗi.
- Lỗi đã phát hiện và cách xử lý:
  - Chặn đọc file ngoài thư mục (kiểu `doc_id=../README.md`) ở endpoint markdown, giờ trả về 404.
  - Test bằng curl trên Git Bash bị lỗi 400 do tiếng Việt sai encoding. Chuyển sang test bằng Python `requests` thì chạy bình thường.

## Điều còn hạn chế

- Một hạn chế cụ thể của phần tôi làm: ngưỡng fallback đang là 0.75, cao hơn điểm của 19/20 câu trong golden set, nên câu nào cũng "rơi" xuống fallback. PageIndex lại chưa có key nên hệ thống cứ giữ kết quả hybrid, và tab Pipeline hiện bước đó màu đỏ gần như mọi lần. Ngoài ra dữ liệu visa hơi cũ: Nhật Bản ra 15 ngày, trong khi quy định mới đã là 45 ngày.
- Nếu có thêm thời gian, thay đổi đầu tiên tôi sẽ thực hiện: hạ ngưỡng về khoảng giữa hai nhóm điểm trong/ngoài domain (tầm 0.4–0.45), rồi cho UI stream câu trả lời từng chữ để đỡ phải chờ.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại trong buổi demo.

- Ngày: 26/09/2026
- Tên thành viên: Nguyễn Đức Thịnh
