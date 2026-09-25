# Prompt thiết kế UI/UX trên Google Stitch — RAG Chatbot Du lịch Việt Nam

Cách dùng: dán **Prompt 0** vào Stitch trước để khóa design system, sau đó dán lần lượt từng prompt màn hình (1 → 6) trong cùng project.
Mọi con số đánh giá (metric, latency, score) trên UI là **dữ liệu mẫu** — thay bằng số thật từ `reports/RESULT.md` sau khi chạy evaluation.

Corpus dùng làm ví dụ (khớp `data/standardized/`):

| Loại | Tài liệu | Nguồn |
| ---- | -------- | ----- |
| legal | LUẬT DU LỊCH (Luật số 09/2017/QH14) | `LUẬT DU LỊCH.pdf` |
| legal | exotravel_vietnam_visa_information | `exotravel_vietnam_visa_information.pdf` |
| legal | vietnam_visitors_notes | `vietnam_visitors_notes.pdf` |
| news | A Complete Guide to Visit Saigon Opera House Ho Chi Minh City | vietnamairlines.com |
| news | The Ultimate Guide to Top Place to Visit in Vietnam Ho Chi Minh City | vietnamairlines.com |
| news | TOP 40 địa điểm du lịch Việt Nam nổi tiếng, hấp dẫn nhất 2026 | vinpearl.com |
| news | Cảnh đẹp Việt Nam – 20 điểm đến đẹp "say lòng" người | vinpearl.com |
| news | Bãi biển đẹp nhất Việt Nam - TOP 20 điểm đến nổi tiếng nhất | vinpearl.com |

---

## Prompt 0 — Tổng quan & design system

```
Design a desktop-first web app (1440px, responsive down to 390px mobile) called "Du Lịch Việt RAG" — a Vietnamese-language RAG chatbot that answers questions about Vietnam tourism: the Vietnam Tourism Law 2017 (Luật Du lịch số 09/2017/QH14), visa and entry rules for foreign visitors, and destination guides (Ho Chi Minh City, famous places, beaches). Every answer carries verifiable citations. All UI copy is in Vietnamese.

Audience: travellers and tour operators/tour guides (chat), plus engineers/graders who need to inspect the retrieval pipeline, ranking and evaluation (transparency is a core feature, not an afterthought).

Visual style: warm, trustworthy, Vietnam-travel inspired but clean and professional (not touristy clip-art). Primary deep jade #0E5E57, accent lantern orange #E4572E, gold highlight #F2B705 for citation highlights, sand background #FAF7F2 in light mode, neutral grays, white cards with 12px radius, soft shadows. Subtle decorative motif: thin line illustration of rice terraces / Ha Long karsts only in empty states and the header. Font: Be Vietnam Pro (full Vietnamese diacritics). Provide light and dark themes. Monospace (JetBrains Mono) for scores, IDs and latencies.

Global layout: left sidebar navigation with 6 items and icons:
1. "Trò chuyện" (Chat)
2. "Pipeline realtime"
3. "Xếp hạng" (Ranking inspector)
4. "Đánh giá A/B" (Evaluation)
5. "Kho dữ liệu" (Knowledge base)
6. "Cấu hình" (Settings)
Top bar: app name with a lotus icon, current model badge "gpt-4o-mini", embedding badge "text-embedding-3-large", a green status dot "ChromaDB: rag_documents — sẵn sàng", theme toggle.

Reusable components to define:
- Retrieval method badge: "dense" (blue), "bm25" (purple), "hybrid" (jade), "pageindex" (orange), "none" (gray).
- Doc type tag: "legal" (jade outline, scale icon) and "news" (orange outline, newspaper icon).
- Citation chip: small rounded superscript like [1], [2]; hover shows source title + snippet; click scrolls to and highlights the source card.
- Source card: title, doc type tag, file name or URL, section (e.g. "Điều 11"), chunk_index, score in monospace, retrieval method badge, expandable snippet with the cited sentence highlighted in gold.
- Score bar: horizontal bar 0–1 with a dashed vertical line marking the fallback threshold 0.75.
- Stage node for pipeline steps: icon, name, status (chờ / đang chạy / xong / bỏ qua / lỗi), latency in ms.
- Toggle pills for bonus features: "HyDE", "Query expansion", "Reranker", "Bộ nhớ hội thoại".
```

---

## Prompt 1 — Màn hình Trò chuyện (chatbot + citation highlighting + conversation memory)

```
Screen "Trò chuyện" — the main chatbot screen of Du Lịch Việt RAG. Three-column layout: sidebar nav (collapsed icons), center chat (60%), right "Nguồn tham khảo" (sources) panel (40%, collapsible).

Center chat:
- Header: title "Hỏi đáp du lịch Việt Nam", subtitle "Luật Du lịch, visa nhập cảnh và cẩm nang điểm đến — mọi câu trả lời đều dẫn nguồn. Không đủ bằng chứng thì chatbot sẽ từ chối."
- Empty state (with rice-terrace line illustration): 4 suggested question chips: "Khách du lịch có những quyền gì theo Luật Du lịch?", "Điều kiện cấp thẻ hướng dẫn viên du lịch quốc tế là gì?", "Công dân Nhật Bản được miễn visa vào Việt Nam bao nhiêu ngày?", "Gợi ý bãi biển đẹp nhất Việt Nam?"
- Conversation example:
  User: "Khách du lịch có những quyền gì theo Luật Du lịch?"
  Assistant (streaming, typing cursor visible): "Theo Luật Du lịch 2017, khách du lịch có các quyền chính sau [1]:
  • Sử dụng dịch vụ du lịch do tổ chức, cá nhân kinh doanh cung cấp hoặc tự đi du lịch.
  • Yêu cầu cung cấp thông tin về chương trình, dịch vụ, điểm đến theo hợp đồng đã ký kết.
  • Được tạo điều kiện thuận lợi về xuất cảnh, nhập cảnh, quá cảnh, hải quan, lưu trú [1].
  • Được bảo đảm an toàn về tính mạng, sức khỏe, tài sản; được cứu hộ, cứu nạn khi khẩn cấp [1].
  • Khiếu nại, tố cáo, khởi kiện và được bồi thường thiệt hại theo quy định của pháp luật [1]."
  Under the answer: a meta row with badge "hybrid", "5 nguồn", "1.8 s", buttons "Xem pipeline", "Xem xếp hạng", thumbs up/down, copy.
  Follow-up user message: "Còn nghĩa vụ thì sao?"
  Above the assistant reply show a subtle "memory" chip with a brain icon: "Đã hiểu là: Nghĩa vụ của khách du lịch theo Luật Du lịch là gì?" (standalone question rewritten from conversation history), with a tooltip "Bộ nhớ hội thoại: dùng 4 lượt gần nhất". The reply cites Điều 12: tuân thủ pháp luật, ứng xử văn minh, tôn trọng phong tục địa phương; thực hiện nội quy khu/điểm du lịch; thanh toán tiền dịch vụ, phí, lệ phí; bồi thường thiệt hại theo pháp luật dân sự [2].
- Safe refusal example (out-of-domain question "Giá Bitcoin hôm nay bao nhiêu?"): an amber-bordered card with a shield icon: "Mình không tìm thấy bằng chứng trong kho tài liệu du lịch để trả lời câu này." Badge "none", small text "Điểm dense cao nhất 0.41 < ngưỡng 0.75 · PageIndex không có kết quả".
- Composer: multiline input "Nhập câu hỏi về du lịch Việt Nam...", send button, and toggle pills above it: "HyDE", "Reranker", "Bộ nhớ hội thoại" (on), plus a top_k stepper (3–10, default 5).

Right "Nguồn tham khảo" panel:
- Sticky header "Nguồn cho câu trả lời đang chọn" with a filter: Tất cả / legal / news.
- 5 numbered source cards; card [1] "LUẬT DU LỊCH — Điều 11. Quyền của khách du lịch" (legal, chunk_index 18, score 0.88, badge hybrid) is expanded and highlighted because the user hovered citation [1]; inside it the exact sentence "Được đối xử bình đẳng; được bảo đảm an toàn về tính mạng, sức khỏe, tài sản khi sử dụng dịch vụ du lịch" is highlighted in gold.
- Other cards: "LUẬT DU LỊCH — Điều 12. Nghĩa vụ của khách du lịch" (legal), "LUẬT DU LỊCH — Điều 13. Bảo đảm an toàn cho khách du lịch" (legal), "vietnam_visitors_notes" (legal, English), "TOP 40 địa điểm du lịch Việt Nam nổi tiếng, hấp dẫn nhất 2026" (news, vinpearl.com), each with a score bar and the threshold marker.
- Cards not cited in the answer are shown dimmed with the label "Được truy xuất nhưng không trích dẫn".
Mobile: sources panel becomes a bottom sheet opened by tapping a citation.
```

---

## Prompt 2 — Màn hình Pipeline realtime

```
Screen "Pipeline realtime" — a live, animated trace of how the current question flows through the RAG pipeline, updating as each stage completes (streaming).

Top: the query being traced "Điều kiện cấp thẻ hướng dẫn viên du lịch quốc tế là gì?" with a "Chạy lại" button and a total latency counter "1 842 ms".

Main area: a horizontal flow diagram (vertical on mobile) of stage nodes connected by animated arrows; completed stages turn jade, the running stage pulses, skipped stages are gray and dashed:
1. "Câu hỏi" (input) →
2. "Viết lại câu hỏi (bộ nhớ hội thoại)" — skipped for first turn →
3. "HyDE / Query expansion" — shows 3 expanded queries, e.g. "yêu cầu cấp thẻ hướng dẫn viên quốc tế", "tiêu chuẩn hướng dẫn viên du lịch quốc tế ngoại ngữ", "Điều 59 Luật Du lịch", 320 ms →
4a. "Dense search" (ChromaDB, text-embedding-3-large, top 10), 140 ms  and in parallel
4b. "BM25" (top 10), 12 ms →
5. "RRF fusion" (k = 60, chạy 1 lần, top 5), 1 ms →
6. "Reranker" (cross-encoder, optional), 210 ms →
7. "Kiểm tra ngưỡng" diamond decision: "Điểm cosine dense cao nhất 0.84 ≥ 0.75 → dùng hybrid"; the alternative branch "< 0.75 → PageIndex fallback" is drawn but dimmed →
8. "Sắp xếp lại context (chống lost-in-the-middle)" →
9. "Sinh câu trả lời" (gpt-4o-mini, temperature 0.3, top_p 0.9), 1 150 ms, with live token counter →
10. "Kiểm tra citation" — "3/3 citation khớp với sources" green check.

Clicking a node opens a right drawer with that stage's input/output as JSON-like cards (list of SearchResult: id, score, retrieval_method, metadata.title, e.g. "LUẬT DU LỊCH — Điều 59. Điều kiện cấp thẻ hướng dẫn viên du lịch").

Bottom: a latency waterfall chart (Gantt style) for all stages, and an event log console in monospace with timestamps, e.g. "10:52:03.114  dense_search  10 kết quả  best_cosine=0.84".
Include an error state example: PageIndex node red with "Provider lỗi — pipeline vẫn trả kết quả hybrid" (the UI must never crash).
```

---

## Prompt 3 — Màn hình Xếp hạng (ranking inspector: dense vs BM25 vs RRF vs reranker)

```
Screen "Xếp hạng" — compare how each retrieval method ranks chunks for one query, to justify hybrid search and the reranker bonus.

Top: query selector (search box + dropdown of recent queries, current: "Công dân Nhật Bản được miễn visa vào Việt Nam bao nhiêu ngày?"), top_k stepper, RRF k input (default 60), toggle "Bật reranker".

Main: four side-by-side ranked columns, each a list of 10 chunk rows (rank #, short title, chunk_index, score in monospace). Example chunk titles: "exotravel_vietnam_visa_information — Countries exempt", "vietnam_visitors_notes — Visas & Entry Requirements", "LUẬT DU LỊCH — Điều 11. Quyền của khách du lịch", "LUẬT DU LỊCH — Điều 10. Các loại khách du lịch":
- "Dense (cosine)" — scores 0–1 with the 0.75 threshold line drawn across the column.
- "BM25" — raw BM25 scores (keyword "Japanese", "visa", "15 days" matches).
- "Hybrid RRF" — rrf score = Σ 1/(k + rank); each row shows a small breakdown "dense #2 + bm25 #1".
- "Reranker" — cross-encoder relevance scores, with green ▲ / red ▼ arrows and the number of positions each chunk moved compared with RRF.
Hovering a chunk highlights the same chunk ID across all four columns with connecting lines (a "bump chart" effect) so users can see rank changes.

Below: a bump chart of rank positions across the 4 methods for the top 10 chunks, and a small stats card: "Trùng lặp top-5 dense ∩ BM25: 3/5", "Chunk được reranker đẩy lên nhiều nhất: +4".
Right drawer on click: full chunk text with query terms highlighted (BM25 matches in purple, semantic match sentence in blue), e.g. "Japanese and South Korean passport holders do not need a visa for a visit up to 15 days."
Note that the corpus mixes Vietnamese and English documents — show a small language tag (VI / EN) on each row.
```

---

## Prompt 4 — Màn hình Đánh giá A/B

```
Screen "Đánh giá A/B" — the evaluation dashboard mirroring the project's RESULT.md report. Label all numbers "Dữ liệu mẫu" with a small tag until real results are loaded.

Header: run info card grid: Ngày đánh giá, Framework "RAGAS 0.4.3", Evaluator model, Generator "gpt-4o-mini", Embedding "text-embedding-3-large", Corpus "3 legal + 5 news", Golden dataset "15 câu", top_k "5", Ngưỡng fallback "0.75 (hiệu chỉnh trên query trong/ngoài domain)".

Section "So sánh cấu hình": two config cards side by side — "Config A — Dense-only" vs "Config B — Hybrid + RRF", with a note "Cùng golden dataset, generator, evaluator, prompt và top_k; chỉ khác chiến lược truy xuất".
Metric table + grouped bar chart for 4 metrics: Faithfulness, Answer relevance, Context recall, Context precision, plus Average, with columns Config A, Config B, Delta B−A (green if positive, red if negative).
A verdict banner: "Cấu hình tốt hơn: Config B" with evidence text and a latency/cost trade-off line.

Section "Thí nghiệm bonus": table with columns Experiment | Baseline | Metric delta | Latency/cost delta | Kết luận, rows: "HyDE", "Query expansion", "Reranker (cross-encoder) vs RRF", "Bộ nhớ hội thoại (follow-up)". Each row has a mini sparkline and a "Xem chi tiết" link.

Section "Câu tệ nhất" (worst performers): table with #, Question, Config, Faithfulness, Relevance, Recall, Precision, Failure stage (tag: retrieval / generation / data), Root cause. Example rows: "Hồ sơ cấp giấy phép kinh doanh dịch vụ lữ hành quốc tế gồm những gì?" (retrieval — Điều 33 bị cắt giữa 2 chunk), "Bãi biển nào đẹp nhất miền Trung?" (data — bài news liệt kê nhưng không so sánh), "Người Anh cần visa không?" (data — thông tin miễn visa trong tài liệu đã cũ, 2017–2018). Clicking a row opens the question, expected answer, expected context, actual answer and retrieved sources side by side.

Section "Khuyến nghị": 3 priority cards (Priority, Action, Evidence, Expected impact, How to verify).
Top-right actions: "Chạy đánh giá" (shows a progress bar 7/15 câu while running), "Xuất RESULT.md".
```

---

## Prompt 5 — Màn hình Kho dữ liệu

```
Screen "Kho dữ liệu" — manage and inspect the corpus that feeds the pipeline: landing → standardized Markdown → chunks → ChromaDB index.

Top KPI tiles: "Tài liệu legal: 3" (requirement ≥ 3, green check), "Bài news: 5" (requirement ≥ 5, green check), "Chunks: —", "Vector dim: 3072", "Collection: rag_documents".
Pipeline status stepper: Thu thập → Chuẩn hóa Markdown → Chunking (recursive, size 500, overlap 50) → Embedding → Index, each with last-run time and a "Chạy lại" button; re-running never creates duplicates (show note "ID ổn định, chạy lại không tạo trùng").

Documents table with tabs "legal" / "news": columns Tên tài liệu, Loại, Ngôn ngữ, Nguồn (file or URL), Kích thước Markdown, Số chunk, Trạng thái (Đã chuẩn hóa / Đã index / Lỗi). Rows:
- LUẬT DU LỊCH — Luật số 09/2017/QH14 (legal, VI, LUẬT DU LỊCH.pdf, 103 KB, 9 chương · 78 điều)
- exotravel_vietnam_visa_information (legal, EN, 6 KB)
- vietnam_visitors_notes (legal, EN, 44 KB)
- A Complete Guide to Visit Saigon Opera House Ho Chi Minh City (news, EN, vietnamairlines.com, 13 KB)
- The Ultimate Guide to Top Place to Visit in Vietnam Ho Chi Minh City (news, EN, vietnamairlines.com, 18 KB)
- TOP 40 địa điểm du lịch Việt Nam nổi tiếng, hấp dẫn nhất 2026 (news, VI, vinpearl.com, 34 KB)
- Cảnh đẹp Việt Nam – 20 điểm đến đẹp "say lòng" người (news, VI, vinpearl.com, 23 KB)
- Bãi biển đẹp nhất Việt Nam - TOP 20 điểm đến nổi tiếng nhất (news, VI, vinpearl.com, 17 KB)
News rows also show the "Crawled" timestamp.
Clicking a document opens a split view: left = rendered Markdown with its structure (for the law: Chương I → Điều 1. Phạm vi điều chỉnh …), right = its chunks list (chunk_index, character count, first 120 chars), with chunk boundaries visualized as colored bands on the Markdown.
Upload zone: drag & drop PDF/DOCX or paste a URL to crawl.
```

---

## Prompt 6 — Màn hình Cấu hình

```
Screen "Cấu hình" — settings grouped in cards, each field with a helper text; secrets are never displayed (show "Đã cấu hình qua .env" status chips only).

Cards:
1. "Mô hình": LLM provider segmented control (OpenAI / Gemini / Anthropic Claude), model field "gpt-4o-mini", temperature slider 0.3, top_p 0.9; embedding provider "openai", model "text-embedding-3-large". API key status chips: OpenAI "Đã cấu hình", Gemini "Chưa cấu hình", Anthropic "Chưa cấu hình", Jina "Chưa cấu hình", PageIndex "Chưa cấu hình".
2. "Truy xuất": top_k (default 5), candidates per retriever (10), RRF k (60), switch "Hybrid + RRF" vs "Dense-only" (used for A/B).
3. "Fallback": threshold slider 0.75 with a calibration mini-chart showing distributions of best dense cosine scores for in-domain queries (e.g. "quyền của khách du lịch", "miễn visa") vs out-of-domain queries (e.g. "giá Bitcoin", "công thức nấu phở") and the chosen cut-off line; switch "PageIndex fallback".
4. "Tính năng nâng cao (bonus)": switches with short descriptions — "HyDE", "Query expansion (3 biến thể)", "Reranker nâng cao" with provider select (Jina / BGE self-host), "Bộ nhớ hội thoại" with a "số lượt nhớ" stepper (default 4), "Highlight câu được trích dẫn".
5. "Triển khai": public URL field and status "Online" for the deployed demo, plus a "Sao chép link demo" button.
Sticky footer: "Lưu cấu hình" primary button and "Khôi phục mặc định".
```
