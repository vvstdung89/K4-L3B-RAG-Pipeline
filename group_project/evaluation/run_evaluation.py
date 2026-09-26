"""A/B evaluation: Config A (dense-only) vs Config B (hybrid + RRF) với RAGAS.

Chạy:
    python -m group_project.evaluation.run_evaluation

Hai config dùng chung golden dataset, generator, prompt, evaluator và top_k;
chỉ khác ``use_reranking``. Kết quả ghi vào ``group_project/evaluation/results/``.
"""

import json
import os
import statistics
import time
import warnings
from pathlib import Path

from dotenv import load_dotenv

from src.task5_semantic_search import semantic_search
from src.task9_retrieval_pipeline import SCORE_THRESHOLD, retrieve
from src.task10_generation import (
    REFUSAL_MESSAGE,
    SYSTEM_PROMPT,
    build_user_message,
    call_llm,
    is_refusal,
    resolve_model,
)


load_dotenv()
os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
warnings.filterwarnings("ignore", category=DeprecationWarning)

HERE = Path(__file__).parent
GOLDEN = HERE / "golden_dataset.json"
OUTPUT = HERE / "results"
TOP_K = 5
EVAL_MODEL = os.getenv("EVAL_MODEL", "gpt-4o-mini")
EVAL_EMBEDDING = os.getenv("EVAL_EMBEDDING_MODEL", "text-embedding-3-small")
CONFIGS = {"A_dense": False, "B_hybrid_rrf": True}
METRICS = ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]

# Query ngoài domain để hiệu chỉnh threshold fallback (cosine dense top-1).
OUT_OF_DOMAIN = [
    "Công thức nấu phở bò",
    "Giá bitcoin hôm nay",
    "Cách cài đặt Python trên Windows",
    "Kết quả trận Real Madrid gặp Barcelona",
    "Lãi suất vay mua nhà ngân hàng Vietcombank",
    "How to train a neural network with PyTorch",
]


def run_config(dataset: list[dict], use_reranking: bool) -> list[dict]:
    rows = []
    for item in dataset:
        start = time.perf_counter()
        chunks = retrieve(item["question"], top_k=TOP_K, use_reranking=use_reranking)
        retrieval_ms = (time.perf_counter() - start) * 1000
        try:
            answer = call_llm(SYSTEM_PROMPT, build_user_message(item["question"], chunks)).strip()
        except Exception as error:  # provider lỗi -> safe refusal như generate_with_citation
            print(f"  ! generation lỗi: {error}")
            answer = REFUSAL_MESSAGE
        rows.append({
            "question": item["question"],
            "answer": answer or REFUSAL_MESSAGE,
            "refused": not answer or is_refusal(answer),
            "contexts": [chunk["content"] for chunk in chunks],
            "source_ids": [chunk["id"] for chunk in chunks],
            "retrieval_method": chunks[0]["retrieval_method"] if chunks else "none",
            "expected_answer": item["expected_answer"],
            "expected_context": item["expected_context"],
            "expected_source": item.get("source", ""),
            "hit_expected_source": any(
                chunk["metadata"].get("source") == item.get("source") for chunk in chunks
            ),
            "latency_ms": round((time.perf_counter() - start) * 1000),
            "retrieval_ms": round(retrieval_ms),
        })
        print(f"  {rows[-1]['latency_ms']:>6} ms  {item['question'][:70]}")
    return rows


def score(rows: list[dict]) -> list[dict]:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from ragas import EvaluationDataset, RunConfig, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        ResponseRelevancy,
    )

    dataset = EvaluationDataset.from_list([
        {
            "user_input": row["question"],
            "response": row["answer"],
            "retrieved_contexts": row["contexts"] or [""],
            "reference": row["expected_answer"],
        }
        for row in rows
    ])
    llm = LangchainLLMWrapper(ChatOpenAI(model=EVAL_MODEL, temperature=0, timeout=60, max_retries=3))
    # Timeout rõ ràng: RAGAS gọi embeddings đồng bộ trong event loop, một request treo sẽ chặn mọi worker.
    embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model=EVAL_EMBEDDING, timeout=30, max_retries=3))
    result = evaluate(
        dataset,
        metrics=[
            Faithfulness(),
            ResponseRelevancy(strictness=1),
            LLMContextRecall(),
            LLMContextPrecisionWithReference(),
        ],
        llm=llm,
        embeddings=embeddings,
        run_config=RunConfig(max_workers=8, timeout=120, max_retries=3),
    )
    frame = result.to_pandas().rename(columns={
        "llm_context_precision_with_reference": "context_precision",
    })
    for row, (_, scored) in zip(rows, frame.iterrows()):
        for metric in METRICS:
            value = scored.get(metric)
            row[metric] = None if value is None or value != value else round(float(value), 4)
    return rows


def summarize(rows: list[dict]) -> dict:
    summary = {}
    for metric in METRICS:
        values = [row[metric] for row in rows if row.get(metric) is not None]
        summary[metric] = round(statistics.mean(values), 4) if values else None
    valid = [value for value in summary.values() if value is not None]
    summary["average"] = round(statistics.mean(valid), 4) if valid else None
    summary["refusals"] = sum(row["refused"] for row in rows)
    summary["source_hit_rate"] = round(sum(row["hit_expected_source"] for row in rows) / len(rows), 4)
    summary["latency_ms_mean"] = round(statistics.mean(row["latency_ms"] for row in rows))
    summary["retrieval_ms_mean"] = round(statistics.mean(row["retrieval_ms"] for row in rows))
    return summary


def calibrate(dataset: list[dict]) -> dict:
    def top1(query: str) -> float:
        results = semantic_search(query, top_k=1)
        return round(results[0]["score"], 4) if results else 0.0

    in_domain = [top1(item["question"]) for item in dataset]
    out_domain = [top1(query) for query in OUT_OF_DOMAIN]
    return {
        "configured_threshold": SCORE_THRESHOLD,
        "in_domain": {"min": min(in_domain), "mean": round(statistics.mean(in_domain), 4), "max": max(in_domain)},
        "out_of_domain": {"min": min(out_domain), "mean": round(statistics.mean(out_domain), 4), "max": max(out_domain)},
        "in_domain_below_threshold": sum(value < SCORE_THRESHOLD for value in in_domain),
        "out_of_domain_scores": dict(zip(OUT_OF_DOMAIN, out_domain)),
    }


def main() -> None:
    dataset = json.loads(GOLDEN.read_text(encoding="utf-8"))
    OUTPUT.mkdir(exist_ok=True)
    report = {
        "evaluation_date": time.strftime("%Y-%m-%d"),
        "golden_size": len(dataset),
        "top_k": TOP_K,
        "generator": "/".join(resolve_model()),
        "evaluator": EVAL_MODEL,
        "evaluator_embedding": EVAL_EMBEDDING,
        "calibration": calibrate(dataset),
        "configs": {},
    }
    for name, use_reranking in CONFIGS.items():
        print(f"== {name}")
        rows = score(run_config(dataset, use_reranking))
        (OUTPUT / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        report["configs"][name] = summarize(rows)
        print(json.dumps(report["configs"][name], ensure_ascii=False))
    (OUTPUT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
