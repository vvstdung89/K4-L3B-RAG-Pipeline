import streamlit as st
from dotenv import load_dotenv


load_dotenv()

from src.task10_generation import LLM_MODEL, LLM_PROVIDER, generate_with_citation  # noqa: E402
from src.task9_retrieval_pipeline import SCORE_THRESHOLD  # noqa: E402


METHOD_COLORS = {
    "hybrid": "green",
    "dense": "blue",
    "bm25": "violet",
    "pageindex": "orange",
    "none": "gray",
}

SUGGESTIONS = [
    "Khách du lịch có những quyền gì theo Luật Du lịch?",
    "Điều kiện cấp thẻ hướng dẫn viên du lịch quốc tế là gì?",
    "Công dân Nhật Bản được miễn visa vào Việt Nam bao nhiêu ngày?",
    "Gợi ý bãi biển đẹp nhất Việt Nam?",
]

st.set_page_config(
    page_title="Du Lịch Việt RAG",
    page_icon="🪷",
    layout="wide",
)

if "messages" not in st.session_state:
    st.session_state.messages = []


def method_badge(method: str) -> str:
    return f":{METHOD_COLORS.get(method, 'gray')}-badge[{method}]"


def render_sources(sources: list[dict], retrieval_source: str) -> None:
    if not sources:
        st.caption(f"Nguồn truy xuất: {method_badge(retrieval_source)} — không có nguồn phù hợp.")
        return
    st.caption(f"Nguồn truy xuất: {method_badge(retrieval_source)} · {len(sources)} chunks")
    with st.expander("Nguồn tham khảo", expanded=False):
        for index, source in enumerate(sources, 1):
            metadata = source["metadata"]
            location = metadata.get("url") or metadata.get("source", "")
            st.markdown(
                f"**[{index}] {metadata.get('title', source['id'])}** "
                f"{method_badge(source['retrieval_method'])} "
                f"`{metadata.get('doc_type', '')}` · chunk #{metadata.get('chunk_index', '?')} · "
                f"score `{source['score']:.4f}`"
            )
            if location:
                st.caption(location)
            snippet = source["content"]
            st.text(snippet[:600] + ("…" if len(snippet) > 600 else ""))
            if index < len(sources):
                st.divider()


with st.sidebar:
    st.title("🪷 Du Lịch Việt RAG")
    st.caption(
        "Hỏi đáp về Luật Du lịch 2017, visa/nhập cảnh và cẩm nang điểm đến Việt Nam. "
        "Mọi câu trả lời đều dẫn nguồn; không đủ bằng chứng thì chatbot từ chối."
    )
    top_k = st.slider("Số chunks", 3, 10, 5)
    st.markdown(f"**Generator:** `{LLM_PROVIDER}/{LLM_MODEL or 'default'}`")
    st.markdown(f"**Fallback threshold (cosine):** `{SCORE_THRESHOLD}`")
    if st.button("Xoá hội thoại", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

st.title("Hỏi đáp du lịch Việt Nam")
st.caption("Luật Du lịch, visa nhập cảnh và cẩm nang điểm đến — câu trả lời kèm citation [n] khớp với danh sách nguồn.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_sources(message.get("sources", []), message.get("retrieval_source", "none"))

query = st.chat_input("Nhập câu hỏi...")

if not st.session_state.messages and not query:
    columns = st.columns(2)
    for index, suggestion in enumerate(SUGGESTIONS):
        if columns[index % 2].button(suggestion, use_container_width=True):
            query = suggestion

if query:
    st.session_state.messages.append({"role": "user", "content": query})

    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Đang truy xuất và sinh câu trả lời..."):
            result = generate_with_citation(query, top_k=top_k)
        st.markdown(result["answer"])
        render_sources(result["sources"], result["retrieval_source"])

    st.session_state.messages.append({
        "role": "assistant",
        "content": result["answer"],
        "sources": result["sources"],
        "retrieval_source": result["retrieval_source"],
    })
