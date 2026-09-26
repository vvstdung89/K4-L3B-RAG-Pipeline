# Du Lịch Việt RAG — UI React

Giao diện React (Vite + Tailwind) cho pipeline RAG. Mọi dữ liệu hiển thị lấy từ backend
`src/api_server.py`, backend đọc `data/standardized`, `chroma_db/` và
`group_project/evaluation/results/`; không có dữ liệu mẫu.

## Chạy local

1. Backend (từ thư mục gốc repo, cần `.env` đã cấu hình và ChromaDB đã index):
   `python -m src.api_server` → http://127.0.0.1:8000
2. Frontend (trong thư mục `src/`):
   `npm install` rồi `npm run dev` → http://localhost:3000 (Vite proxy `/api` sang cổng 8000,
   đổi bằng biến `RAG_API_URL`).

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
