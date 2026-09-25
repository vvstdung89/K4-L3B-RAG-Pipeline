# Kết quả đánh giá RAG

## Thông tin lần chạy

| Trường | Giá trị |
|---|---|
| Ngày đánh giá | 2026-09-25 (thời điểm chạy UTC: 06:58:10) |
| Bộ công cụ và phiên bản | Trình đánh giá Gemini LLM-as-a-judge tự xây dựng; Google GenAI SDK 2.24.0; ChromaDB 1.5.9 |
| Mô hình đánh giá | `gemini-3.5-flash-lite` |
| Mô hình sinh câu trả lời | `gemini-3.5-flash-lite` |
| Mô hình embedding | `gemini-embedding-001`, 3072 chiều |
| Phiên bản corpus/commit | Corpus đã chuẩn hóa tại Git commit `455e2d1` |
| Số câu trong golden dataset | 15 |
| `top_k` | 5 |
| Ngưỡng fallback và hiệu chỉnh | Tắt PageIndex fallback ở cả hai nhánh A/B (`score_threshold=-1.0`) để cô lập chiến lược retrieval; ngưỡng production vẫn là 0.3 và chưa được hiệu chỉnh |
| Môi trường chạy | Python 3.14.7 (nằm ngoài phạm vi Python `<3.14` khai báo trong `pyproject.toml`) |

Cả hai cấu hình đã chạy đủ 15 case (30 lượt sinh câu trả lời và 30 lượt đánh giá). Để phù hợp quota free-tier, embedding được gửi theo batch 100 chunk, cách nhau 60 giây; các lượt sinh và chấm câu trả lời được giãn cách 4 giây. Trong lần thử ban đầu, quota embedding trả HTTP 429; tiến trình tiếp tục từ checkpoint 100 chunk đã lưu và hoàn tất đủ 540/540 chunk. Sau đó, lượt chạy A/B hoàn tất mà không gặp lỗi quota. Điểm và nhãn lỗi do LLM-as-a-judge tạo ra; nên đối chiếu với kết quả từng case đã lưu.

## Cấu hình so sánh

- **Cấu hình A — dense-only:** Tìm kiếm dense bằng Gemini, `top_k=5`.
- **Cấu hình B — hybrid + RRF:** Tìm kiếm dense bằng Gemini kết hợp BM25, sau đó gộp thứ hạng bằng RRF, `top_k=5`.

Cả hai nhánh dùng cùng corpus, golden dataset, mô hình sinh, mô hình đánh giá, prompt và `top_k`. PageIndex fallback được tắt ở cả hai nhánh. Biến duy nhất trong phép so sánh A/B là có dùng BM25+RRF hay không.

## Điểm tổng hợp (Overall scores)

| Metric | Cấu hình A | Cấu hình B | Chênh lệch B−A |
|---|---:|---:|---:|
| Faithfulness (độ bám sát ngữ cảnh) | 1.000 | 0.967 | -0.033 |
| Answer relevance (mức liên quan của câu trả lời) | 0.907 | 0.811 | -0.095 |
| Context recall (độ bao phủ bằng chứng) | 0.800 | 0.733 | -0.067 |
| Context precision (độ tập trung của ngữ cảnh) | 0.600 | 0.463 | -0.137 |
| **Trung bình** | **0.827** | **0.744** | **-0.083** |

## So sánh A/B (A/B comparison)

- **Cấu hình có điểm cao hơn:** Cấu hình A, dense-only, đạt điểm cao hơn ở cả bốn metric trong lần chạy này.
- **Bằng chứng:** Điểm trung bình của A là 0.827, của B là 0.744. Hybrid+RRF làm context precision giảm 0.137 và answer relevance giảm 0.095. File kết quả từng case có 30 câu trả lời, ID các chunk được truy xuất, bốn điểm số và ghi chú của evaluator.
- **Đánh đổi latency/chi phí:** Lần chạy này không ghi latency từng request hoặc số tiền tính phí. Hệ thống dùng Gemini API free-tier; giới hạn tốc độ tạo ra khoảng nghỉ 60 giây sau mỗi 100 chunk embedding và 4 giây giữa các lượt gọi mô hình sinh/đánh giá. Đây là thời gian chờ để tuân thủ quota, không phải latency đo được của mô hình. Quota embedding free-tier đã chạm giới hạn trong lúc thiết lập, nhưng tiến trình tiếp tục và hoàn tất.

## Ba case có kết quả kém nhất (Worst performers)

Đây là ba câu có điểm trung bình thấp nhất khi lấy trung bình các metric của cả cấu hình A và B. Điểm chi tiết từng cấu hình và ghi chú của evaluator nằm trong `reports/gemini_eval_results.json`.

| # | Câu hỏi | A (faithfulness / relevance / recall / precision) | B (faithfulness / relevance / recall / precision) | Giai đoạn lỗi | Bằng chứng về nguyên nhân gốc |
|---:|---|---|---|---|---|
| 1 | Ai được hành nghề hướng dẫn du lịch theo định nghĩa trong Luật Du lịch? | 1.00 / 0.50 / 0.00 / 0.80 | 1.00 / 0.20 / 0.00 / 0.20 | Retrieval | Bằng chứng trả lời nằm trong `legal/LUẬT DU LỊCH.md::chunk-6`, nhưng không cấu hình nào đưa chunk này vào top 5. Cả hai danh sách lại có các chunk phía sau nói về phân loại và trách nhiệm của hướng dẫn viên. Cụm “hướng dẫn viên du lịch” lặp lại khiến hệ thống lấy nhầm đoạn gần nghĩa/từ khóa. |
| 2 | Theo Luật Du lịch, khu du lịch được chia thành những cấp nào? | 1.00 / 0.50 / 0.00 / 0.10 | 1.00 / 1.00 / 0.00 / 0.20 | Retrieval | Định nghĩa cần tìm nằm trong `legal/LUẬT DU LỊCH.md::chunk-5`, nhưng cả hai nhánh đều không lấy được chunk này. Các kết quả đầu là những đoạn khác trong luật có nhắc đến khu du lịch, làm precision thấp và không bao phủ bằng chứng chuẩn. |
| 3 | Theo tài liệu EXO Travel, khách mang hộ chiếu Thái Lan hoặc Singapore có thể lưu trú miễn visa tối đa bao lâu? | 1.00 / 0.80 / 0.50 / 0.50 | 1.00 / 0.50 / 0.00 / 0.20 | Retrieval | Danh sách quốc gia được miễn visa bị chia giữa hai chunk liền kề 1–2 của `exotravel_vietnam_visa_information.md`. Hệ thống lấy chunk 2, có thông tin về Singapore nhưng thiếu điều khoản về hộ chiếu Thái Lan nằm cuối chunk 1. |

## Đề xuất (Recommendations)

| Ưu tiên | Hành động | Bằng chứng | Tác động dự kiến | Cách xác minh |
|---:|---|---|---|---|
| 1 | Điều chỉnh chunking để giữ ranh giới điều/khoản của văn bản luật và gắn metadata điều/khoản cho từng chunk pháp lý. | Hai case kém nhất cần định nghĩa ở chunk 5 và 6 của tài liệu luật; cả hai đều vắng mặt trong top 5 của cả hai cấu hình. | Tăng khả năng truy xuất đúng định nghĩa pháp lý và giảm các đoạn gần nghĩa nhưng không chứa câu trả lời. | Tạo lại index, chạy lại 15 case với cùng thiết lập A/B; xác nhận case 3 và 4 lấy được chunk bằng chứng chuẩn, rồi so sánh recall và precision. |
| 2 | Không tách danh sách quốc gia miễn visa giữa các chunk; giữ nguyên đoạn văn hoặc tăng overlap để chunk chứa đủ danh sách. | Case visa lấy chunk 2 có Singapore nhưng thiếu điều khoản về Thái Lan ở cuối chunk 1. | Tăng độ đầy đủ bằng chứng cho câu hỏi có nhiều thực thể. | Tạo lại index và chạy lại case 5; kiểm tra top 5 có cả hai điều khoản hộ chiếu và context recall đạt 1.0. |
| 3 | Sửa mâu thuẫn giữa tiêu đề Saigon Opera House và nội dung về Nhà hát Lớn Hà Nội trong `news/article_01.md` và metadata. | Case 11: cấu hình A truy xuất được bằng chứng giá vé (recall 1.0), còn B từ chối dù ngữ cảnh có thông tin liên quan; evaluator ghi nhận khả năng nhầm Hà Nội với Sài Gòn. | Giảm nhầm lẫn nguồn/địa điểm và giúp câu trả lời bám đúng địa điểm được hỏi. | Sửa hoặc tách tài liệu, tạo lại index, chạy lại case 11 trên cả hai cấu hình; kiểm tra câu trả lời, citation, relevance và precision. |

## Thử nghiệm bổ sung

| Thử nghiệm | Mốc so sánh | Chênh lệch metric | Chênh lệch latency/chi phí | Kết luận |
|---|---|---:|---:|---|
| Dense-only so với hybrid + RRF | Dense-only (A) | Điểm trung bình B thấp hơn 0.083; cả bốn delta đều âm | Chưa đo; hai cấu hình dùng cùng model Gemini và cùng cơ chế giãn request theo free-tier | Trên corpus và lần chạy này, dense-only tốt hơn. Tạm chọn A; chạy lại sau khi sửa ranh giới chunk và mâu thuẫn nguồn trước khi chốt cấu hình. |
