# Du Lịch Việt RAG — UI React

Giao diện React (Vite + Tailwind) cho pipeline RAG. Mọi dữ liệu hiển thị lấy từ backend
`src/api_server.py`, backend đọc `data/standardized`, `chroma_db/` và
`reports/demo_eval_results.json` (ưu tiên) hoặc `reports/gemini_eval_results.json`;
không có dữ liệu mẫu. Giao diện được lấy từ
nhánh `Thihn/02468` (commit `e7c6bb5`), API được điều chỉnh theo các task trên `main`.
Các file `task*.py` không thay đổi. Kết quả chưa đo như latency/source hit rate
hiển thị `—`; điểm Gemini judge không được ghi nhãn là RAGAS.

## Chạy local

0. Cài dependencies Python theo README gốc (bao gồm FastAPI và Uvicorn).
   Frontend cần Node.js 22.12+ hoặc 24+.
1. Backend (từ thư mục gốc repo, cần `.env` đã cấu hình và ChromaDB đã index):
   `python -m src.api_server` → http://127.0.0.1:8000
2. Frontend (trong thư mục `src/`):
   `npm ci` rồi `npm run dev` → http://localhost:3000 (Vite proxy `/api` sang cổng 8000,
   đổi bằng biến `RAG_API_URL`).

Kho dữ liệu, cấu hình và kết quả A/B có thể xem trước khi index. Nếu ChromaDB rỗng,
chat/xếp hạng hiển thị yêu cầu chạy `python -m src.task4_chunking_indexing`.
API key chỉ nằm trong `.env` ở root; không đưa vào biến `VITE_*` hoặc frontend.
Backend chạy local trên `127.0.0.1`; frontend proxy gửi request tới backend.

UI giữ số citation theo thứ tự context sau `reorder_for_llm`, chuyển cách hiển thị
`[Document N]` thành `[N]` cho nút citation. API dùng các hàm search, RRF, reorder,
format context và LLM hiện có để cung cấp trace; không thay đổi thuật toán task.

Kiểm tra frontend: `npm run lint` và `npm run build` trong thư mục `src/`.
UI Streamlit: chạy `streamlit run app.py` từ root.

## Chạy lại bằng OpenAI, giữ nguyên các task

Trong `.env` ở root, đặt `EMBEDDING_PROVIDER=openai`,
`EMBEDDING_MODEL=text-embedding-3-large`, `LLM_PROVIDER=openai`,
`LLM_MODEL=gpt-4o-mini`, `EVALUATOR_MODEL=gpt-4o-mini` và `OPENAI_API_KEY`.
Model embedding này phù hợp với 3072 chiều đang cố định trong task4.

```powershell
python -m scripts.index_demo
python -m scripts.evaluate_demo --fresh
python -m src.api_server
```

`index_demo` gọi các hàm task4 hiện có, đổi URL `null` thành chuỗi rỗng khi ghi
metadata để tương thích Chroma 0.5. `evaluate_demo` dùng nguyên task10 và rubric
của task11, nhưng gọi OpenAI judge vì task11 chỉ có Gemini judge. Bỏ `--fresh`
để tiếp tục checkpoint cùng cấu hình/corpus. Kết quả và báo cáo được ghi vào
`reports/demo_eval_results.json`, `reports/DEMO_RESULT.md`; kết quả Gemini cũ được giữ lại.

## API

| Endpoint | Dùng cho |
| --- | --- |
| `GET /api/config` | Header, Cấu hình, Kho dữ liệu |
| `GET /api/documents` | Kho dữ liệu (danh sách file + số chunk trong Chroma) |
| `GET /api/documents/chunks?doc_id=` | Xem chunk của một tài liệu |
| `GET /api/documents/markdown?doc_id=` | Mở file markdown đã chuẩn hoá |
| `POST /api/chat` | Trò chuyện + trace cho Pipeline |
| `POST /api/retrieve` | Xếp hạng (dense / BM25 / RRF, không gọi LLM) |
| `GET /api/evaluation` | Đánh giá A/B, Sidebar |
