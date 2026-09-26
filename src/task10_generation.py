"""
Task 10 — Generation có citation.

Hướng dẫn:
    1. Retrieve top-k chunks.
    2. Reorder để giảm lost-in-the-middle.
    3. Format context kèm title và source.
    4. Gọi provider được chọn trong .env.
    5. Trả answer, sources và retrieval_source.

Nếu context không đủ hoặc provider lỗi, trả safe refusal; không bịa thông tin.
"""

import os
import re
from collections.abc import Iterator

from dotenv import load_dotenv

from .task9_retrieval_pipeline import retrieve


load_dotenv()

TOP_K = 5
TOP_P = 0.9
TEMPERATURE = 0.3

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()
LLM_MODEL = os.getenv("LLM_MODEL", "").strip()
DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash",
    "anthropic": "claude-sonnet-5",
}

REFUSAL_MESSAGE = "Tôi không thể xác minh thông tin này từ nguồn hiện có."

SYSTEM_PROMPT = f"""Bạn là trợ lý tra cứu du lịch Việt Nam (Luật Du lịch 2017, visa/nhập cảnh, cẩm nang điểm đến).
Quy tắc bắt buộc:
- Chỉ trả lời từ các Document trong context. Không dùng kiến thức bên ngoài.
- Mỗi câu khẳng định phải kết thúc bằng citation dạng [n], n là số của Document chứa bằng chứng. Có thể ghép [1][3].
- Không trích dẫn số Document không có trong context.
- Trả lời bằng tiếng Việt, ngắn gọn, dùng gạch đầu dòng khi liệt kê. Tài liệu tiếng Anh thì dịch ý sang tiếng Việt.
- Nếu context không chứa bằng chứng cho câu hỏi, chỉ trả lời đúng một câu: "{REFUSAL_MESSAGE}\""""


def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """Đưa chunks quan trọng về đầu và cuối context (không sửa list gốc)."""
    if len(chunks) <= 2:
        return list(chunks)
    front = chunks[::2]
    back = chunks[1::2]
    return front + back[::-1]


def format_context(chunks: list[dict], labels: dict[str, int] | None = None) -> str:
    """Tạo context có title và source label.

    ``labels`` map chunk id -> số citation. Khi context đã reorder, số citation
    vẫn là thứ hạng gốc để [n] khớp với sources[n-1].
    """
    parts = []
    for position, chunk in enumerate(chunks, 1):
        metadata = chunk["metadata"]
        number = labels.get(chunk["id"], position) if labels else position
        url = f" | URL: {metadata['url']}" if metadata.get("url") else ""
        parts.append(
            f"[Document {number} | Title: {metadata['title']} | "
            f"Source: {metadata['source']}{url}]\n{chunk['content']}"
        )
    return "\n\n---\n\n".join(parts)


def resolve_model(provider: str | None = None, model: str | None = None) -> tuple[str, str]:
    provider = (provider or LLM_PROVIDER).lower()
    if provider == "claude":
        provider = "anthropic"
    return provider, (model or LLM_MODEL or DEFAULT_MODELS.get(provider, ""))


def call_llm(
    system_prompt: str,
    user_message: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    temperature: float = TEMPERATURE,
    top_p: float = TOP_P,
    json_mode: bool = False,
) -> str:
    """Gọi OpenAI, Gemini hoặc Anthropic theo cấu hình; trả text thuần."""
    provider, model = resolve_model(provider, model)
    if provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=60, max_retries=2)
        extra = {"response_format": {"type": "json_object"}} if json_mode else {}
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            top_p=top_p,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            **extra,
        )
        return response.choices[0].message.content or ""
    if provider == "gemini":
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model=model,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                top_p=top_p,
                response_mime_type="application/json" if json_mode else None,
            ),
        )
        return response.text or ""
    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model=model,
            max_tokens=1500,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return "".join(block.text for block in response.content if block.type == "text")
    raise ValueError(f"LLM_PROVIDER không hỗ trợ: {provider}")


def stream_llm(
    system_prompt: str,
    user_message: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    temperature: float = TEMPERATURE,
    top_p: float = TOP_P,
) -> Iterator[str]:
    """Stream token từ OpenAI; provider khác trả cả câu trả lời một lần."""
    provider, model = resolve_model(provider, model)
    if provider != "openai":
        yield call_llm(system_prompt, user_message, provider=provider, model=model,
                       temperature=temperature, top_p=top_p)
        return
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=60, max_retries=2)
    stream = client.chat.completions.create(
        model=model,
        temperature=temperature,
        top_p=top_p,
        stream=True,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    for event in stream:
        if event.choices and event.choices[0].delta.content:
            yield event.choices[0].delta.content


def build_user_message(query: str, chunks: list[dict]) -> str:
    labels = {chunk["id"]: index for index, chunk in enumerate(chunks, 1)}
    context = format_context(reorder_for_llm(chunks), labels)
    return f"Context:\n{context}\n\nCâu hỏi: {query}"


def is_refusal(answer: str) -> bool:
    return REFUSAL_MESSAGE.lower().rstrip(".") in answer.lower()


def cited_numbers(answer: str, source_count: int) -> list[int]:
    """Các số [n] hợp lệ xuất hiện trong câu trả lời."""
    numbers = {int(value) for value in re.findall(r"\[(\d+)\]", answer)}
    return sorted(number for number in numbers if 1 <= number <= source_count)


def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """Trả về GenerationResult."""
    refusal = {"answer": REFUSAL_MESSAGE, "sources": [], "retrieval_source": "none"}
    try:
        chunks = retrieve(query, top_k=top_k)
    except Exception:
        return refusal
    if not chunks:
        return refusal
    try:
        answer = call_llm(SYSTEM_PROMPT, build_user_message(query, chunks)).strip()
    except Exception:
        return refusal
    if not answer or is_refusal(answer):
        return refusal
    return {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": chunks[0]["retrieval_method"],
    }


if __name__ == "__main__":
    result = generate_with_citation("Khách du lịch có những quyền gì?")
    print(result["answer"])
    for index, source in enumerate(result["sources"], 1):
        print(f"[{index}] {source['metadata']['title']} #{source['metadata']['chunk_index']}")
