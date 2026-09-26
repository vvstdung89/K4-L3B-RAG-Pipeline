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

from dotenv import load_dotenv

from .task9_retrieval_pipeline import SCORE_THRESHOLD, retrieve


load_dotenv()

TOP_K = 5
TOP_P = 0.9
TEMPERATURE = 0.3

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")

SYSTEM_PROMPT = """Trả lời chỉ từ context được cung cấp.
Mỗi khẳng định phải có citation dạng [Document N]. Nếu thiếu evidence, hãy từ chối xác minh.
Không suy diễn hoặc dùng kiến thức ngoài context."""
SAFE_REFUSAL = "Tôi không thể xác minh thông tin này từ nguồn hiện có."


def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """Đưa chunks quan trọng về đầu và cuối context."""
    # Interleave best, worst, second-best, second-worst while preserving identity.
    ordered = list(chunks)
    result = []
    left, right = 0, len(ordered) - 1
    while left <= right:
        result.append(ordered[left]); left += 1
        if left <= right:
            result.append(ordered[right]); right -= 1
    return result


def format_context(chunks: list[dict]) -> str:
    """Tạo context có title và source label."""
    parts = []
    for index, chunk in enumerate(chunks, 1):
        metadata = chunk["metadata"]
        title = metadata.get("title") or metadata.get("source") or "Untitled"
        source = metadata.get("source") or "unknown"
        parts.append(f"[Document {index} | Title: {title} | Source: {source} | ID: {chunk['id']}]\n{chunk['content']}")
    return "\n\n---\n\n".join(parts)


def call_llm(system_prompt: str, user_message: str) -> str:
    """Gọi OpenAI, Gemini hoặc Anthropic theo cấu hình."""
    provider = LLM_PROVIDER.lower()
    if provider == "openai":
        from openai import OpenAI
        model = LLM_MODEL or "gpt-4o-mini"
        response = OpenAI().chat.completions.create(model=model, temperature=TEMPERATURE, top_p=TOP_P,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}])
        return response.choices[0].message.content or ""
    if provider == "gemini":
        from google import genai
        from google.genai import types
        client = genai.Client()
        response = client.models.generate_content(model=LLM_MODEL or "gemini-2.5-flash",
            contents=user_message,
            config=types.GenerateContentConfig(system_instruction=system_prompt, temperature=TEMPERATURE, top_p=TOP_P))
        return response.text or ""
    if provider == "anthropic":
        from anthropic import Anthropic
        response = Anthropic().messages.create(model=LLM_MODEL or "claude-3-5-haiku-latest", max_tokens=1200,
            temperature=TEMPERATURE, system=system_prompt, messages=[{"role": "user", "content": user_message}])
        return "\n".join(block.text for block in response.content if getattr(block, "type", None) == "text")
    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def generate_for_config(
    query: str,
    top_k: int = TOP_K,
    use_reranking: bool = True,
    score_threshold: float = SCORE_THRESHOLD,
) -> dict:
    """Trả về GenerationResult."""
    if top_k <= 0 or not query.strip():
        return {"answer": SAFE_REFUSAL, "sources": [], "retrieval_source": "none"}
    try:
        chunks = retrieve(query, top_k=top_k, use_reranking=use_reranking, score_threshold=score_threshold)
    except Exception:
        chunks = []
    if not chunks:
        return {"answer": SAFE_REFUSAL, "sources": [], "retrieval_source": "none"}
    ordered = reorder_for_llm(chunks)
    context = format_context(ordered)
    try:
        answer = call_llm(SYSTEM_PROMPT, f"Context:\n{context}\n\nQuestion: {query}")
        answer = answer.strip() if isinstance(answer, str) else ""
    except Exception:
        answer = ""
    if not answer:
        answer = SAFE_REFUSAL
    method = chunks[0].get("retrieval_method")
    retrieval_source = "pageindex" if method == "pageindex" else "hybrid"
    return {"answer": answer, "sources": chunks, "retrieval_source": retrieval_source}


def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """Public default generation interface, preserving the existing contract."""
    return generate_for_config(query, top_k=top_k, use_reranking=True)


if __name__ == "__main__":
    print(generate_with_citation("test query"))
