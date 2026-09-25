"""
Task 2 — Crawl bài viết/thông báo bằng Firecrawl.

Hướng dẫn:
    1. Điền FIRECRAWL_API_KEY trong file .env.
    2. Chạy: python -m src.task2_crawl_news
    3. Mỗi bài được lưu thành một JSON trong data/landing/news/.
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from firecrawl import AsyncFirecrawl


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data" / "landing" / "news"

ARTICLE_URLS = [
    "https://www.vietnamairlines.com/au/en/plan-book/travel/travel-guide/saigon-opera-house-ho-chi-minh-city",
    "https://www.vietnamairlines.com/au/en/plan-book/travel/travel-guide/place-to-visit-in-vietnam-ho-chi-minh",
    "https://vinpearl.com/vi/40-dia-diem-du-lich-viet-nam-noi-tieng-nhat-dinh-nen-den-mot-lan",
    "https://vinpearl.com/vi/top-20-canh-dep-viet-nam-duoc-khach-du-lich-yeu-thich-nhat",
    "https://vinpearl.com/vi/20-bai-bien-dep-nhat-viet-nam-duoc-nhieu-du-khach-yeu-thich-nhat",
]


async def crawl_article(url: str, firecrawl: AsyncFirecrawl) -> dict:
    result = await firecrawl.scrape(url, formats=["markdown"])
    metadata = result.metadata
    return {
        "url": url,
        "title": getattr(metadata, "title", None) or "Unknown",
        "date_crawled": datetime.now(timezone.utc).isoformat(),
        "content_markdown": result.markdown or "",
    }


async def crawl_all() -> None:
    """Crawl và lưu từng bài thành một file JSON."""
    api_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "Thiếu FIRECRAWL_API_KEY. Sao chép .env.example thành .env, "
            "rồi điền API key Firecrawl vào đó."
        )
    if "your-api-key" in api_key.lower() or "placeholder" in api_key.lower():
        raise RuntimeError(
            "FIRECRAWL_API_KEY vẫn là giá trị mẫu. Hãy thay bằng API key "
            "thật trong .env."
        )

    firecrawl = AsyncFirecrawl(api_key=api_key)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0

    for index, url in enumerate(ARTICLE_URLS, 1):
        try:
            article = await crawl_article(url, firecrawl)
            output = DATA_DIR / f"article_{index:02d}.json"
            output.write_text(
                json.dumps(article, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"Saved: {output}")
        except Exception as error:
            error_message = str(error)
            lowered_error = error_message.lower()
            if "unauthorized" in lowered_error or "invalid token" in lowered_error:
                raise RuntimeError(
                    "Firecrawl từ chối FIRECRAWL_API_KEY (401 Unauthorized). "
                    "Hãy tạo hoặc sao chép lại key trong Firecrawl Dashboard, "
                    "thay giá trị trong .env, rồi chạy lại. Nếu vừa thay key, "
                    "kiểm tra biến FIRECRAWL_API_KEY đã export trong terminal "
                    "vì biến môi trường có ưu tiên hơn .env."
                ) from None
            failures += 1
            print(f"Failed: {url} — {error}")

    if failures:
        raise RuntimeError(f"Có {failures} URL crawl thất bại.")


if __name__ == "__main__":
    try:
        asyncio.run(crawl_all())
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
