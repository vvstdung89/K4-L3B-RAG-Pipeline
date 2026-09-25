"""
Task 3 — Chuẩn hóa dữ liệu sang Markdown.

Hướng dẫn:
    1. Dùng MarkItDown để convert PDF/DOCX.
    2. Đọc JSON và giữ metadata ở đầu file Markdown.
    3. Giữ cấu trúc thư mục legal/ và news/.
    4. Không tạo file rỗng hoặc file trùng khi chạy lại.

Cài đặt:
    Dependency MarkItDown đã được khai báo trong pyproject.toml.
    
-> Hoặc dùng công cụ nào bạn quen khác Markitdown
"""

from pathlib import Path
import json
import os
import re
import tempfile
import zipfile
from xml.etree import ElementTree
from typing import Any
from html import unescape


LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"
LEGAL_EXTENSIONS = {".pdf", ".doc", ".docx"}


def _convert_with_fallback(source: Path) -> str:
    """Extract text with locally available libraries if MarkItDown is absent."""
    if source.suffix.lower() == ".pdf":
        try:
            import pymupdf
        except ImportError as exc:
            raise RuntimeError("PDF fallback requires PyMuPDF") from exc
        with pymupdf.open(source) as pdf:
            return "\n\n".join(page.get_text() for page in pdf)
    if source.suffix.lower() == ".docx":
        # DOCX is a ZIP of XML parts; extracting paragraph text avoids another
        # dependency and preserves paragraph boundaries.
        with zipfile.ZipFile(source) as archive:
            document = ElementTree.fromstring(archive.read("word/document.xml"))
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = []
        for paragraph in document.findall(".//w:p", namespace):
            text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace))
            if text.strip():
                paragraphs.append(text)
        return "\n\n".join(paragraphs)
    raise RuntimeError(
        f"Converting {source.suffix} requires the 'markitdown[pdf]' dependency"
    )


def _write_markdown(path: Path, content: str) -> bool:
    """Write non-empty Markdown atomically; return False for blank content."""
    content = content.strip()
    if not content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement prevents a failed conversion from leaving a partial file.
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
    ) as stream:
        temporary_path = Path(stream.name)
        stream.write(content + "\n")
    try:
        os.replace(temporary_path, path)
        path.chmod(0o664)
    finally:
        temporary_path.unlink(missing_ok=True)
    return True


def convert_legal_docs() -> None:
    """Convert legal PDF/Word files, retaining any subdirectory structure."""
    legal_dir = LANDING_DIR / "legal"
    if not legal_dir.exists():
        return
    inputs = sorted(
        path for path in legal_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in LEGAL_EXTENSIONS
    )
    if not inputs:
        return

    try:
        from markitdown import MarkItDown
        converter = MarkItDown()
    except ImportError:
        converter = None
    for source in inputs:
        target = OUTPUT_DIR / "legal" / source.relative_to(legal_dir).with_suffix(".md")
        try:
            if converter is None:
                text = _convert_with_fallback(source)
            else:
                result = converter.convert(str(source))
                text = result.text_content or ""
                if not text.strip():
                    text = _convert_with_fallback(source)
        except Exception as exc:
            raise RuntimeError(f"Failed to convert legal document {source}") from exc
        _write_markdown(target, text)


def _required_string(data: dict[str, Any], key: str, source: Path) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{source}: expected non-empty string field '{key}'")
    return value.strip()


_NOISE_HEADINGS = (
    "## find a flight", "## explore more", "## bài viết dành cho bạn",
    "## bài viết liên quan", "## ưu đãi liên quan", "## bài viết mới nhất",
    "### vietnam airlines", "### support", "### legal",
    "### useful information", "### agency & partner", "### cargo",
)
_NOISE_TEXT = (
    "skip to main content", "select region and language", "booking and service",
    "please enter your search keyword", "suggested results", "no search results",
    "lịch sử tìm kiếm", "từ khóa phổ biến", "cẩm nang du lịch", "đăng nhập",
    "đăng ký", "cookie settings", "cancel confirmation", "are you sure to cancel",
    "recaptcha requires verification", "protected by recaptcha", "chat with neo",
    "stay on united states", "you are being redirected", "you are about to leave",
    "would you like to continue", "loading", "noyes", "yesno", "giá công bố",
    "giá chỉ từ", "đặt ngay", "/đêm", "vinholidays",
)
_MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\((?:[^()]|\([^()]*\))*\)")
_MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\((?:[^()]|\([^()]*\))*\)")


def _clean_article_markdown(markdown: str) -> str:
    """Remove crawler chrome and image/link markup while keeping article text."""
    markdown = unescape(markdown).replace("\r\n", "\n").replace("\r", "\n")
    lines = markdown.splitlines()

    # Crawlers often capture full site navigation before the article. Start at
    # its first H1 and stop before the site's recommendations or footer.
    first_heading = next(
        (i for i, line in enumerate(lines) if re.match(r"^#\s+\S", line)), 0
    )
    lines = lines[first_heading:]
    cleaned = []
    in_toc = False
    for line in lines:
        if any(line.strip().lower().startswith(marker) for marker in _NOISE_HEADINGS):
            break
        lowered = line.strip().lower()
        if re.fullmatch(r"(?:#{1,6}\s*)?(?:table of contents|mục lục)", lowered):
            in_toc = True
            continue
        if in_toc:
            if re.match(r"^#{1,3}\s+(?:1[.\\]|điểm du lịch nào)", lowered):
                in_toc = False
            else:
                continue
        if any(noise in lowered for noise in _NOISE_TEXT):
            continue
        # Image descriptions are often emitted as separate italic captions.
        if (
            lowered.startswith("_") and lowered.endswith("_")
        ) or "(ảnh:" in lowered or "(source:" in lowered:
            continue
        # Images are decorative/caption-heavy and are not useful retrieval text.
        line = _MARKDOWN_IMAGE.sub("", line)
        # Retain link labels (addresses, article prose) but discard URL targets.
        line = _MARKDOWN_LINK.sub(r"\1", line)
        line = re.sub(r"<https?://[^>]+>|https?://\S+", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if line and not re.fullmatch(r"[/|•\-\s]+", line) and "[](" not in line:
            cleaned.append(line)

    # Collapse blank runs while preserving paragraph and heading boundaries.
    result = []
    for line in cleaned:
        if line or (result and result[-1]):
            result.append(line)
    return "\n".join(result).strip()


def convert_news_articles() -> None:
    """Convert crawled news JSON to Markdown with source metadata up front."""
    news_dir = LANDING_DIR / "news"
    if not news_dir.exists():
        return
    for source in sorted(news_dir.rglob("*.json")):
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Unable to read valid JSON from {source}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{source}: expected a JSON object")

        title = _required_string(data, "title", source)
        url = _required_string(data, "url", source)
        date_crawled = _required_string(data, "date_crawled", source)
        body = _clean_article_markdown(
            _required_string(data, "content_markdown", source)
        )
        if not body:
            raise ValueError(f"{source}: article body is empty after cleanup")
        markdown = (
            f"# {title}\n\n"
            f"**Source:** {url}\n\n"
            f"**Crawled:** {date_crawled}\n\n"
            "---\n\n"
            f"{body}\n"
        )
        target = OUTPUT_DIR / "news" / source.relative_to(news_dir).with_suffix(".md")
        _write_markdown(target, markdown)


def convert_all() -> None:
    """Convert toàn bộ dữ liệu landing."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    convert_legal_docs()
    convert_news_articles()
    print(f"Saved Markdown to: {OUTPUT_DIR}")


if __name__ == "__main__":
    convert_all()
