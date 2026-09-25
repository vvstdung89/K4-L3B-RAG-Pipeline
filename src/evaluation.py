"""Reproducible RAGAS evaluation: dense-only versus hybrid + RRF.

python -m src.evaluation --output group_project/evaluation
Completed rows are checkpointed and reused only for identical data/code/config.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import tempfile

from .chatbot import run_question
from . import task10_generation as generation
from .task4_chunking_indexing import CHUNKS_PATH, EMBEDDING_MODEL, EMBEDDING_PROVIDER
from .task9_retrieval_pipeline import SCORE_THRESHOLD

ROOT = Path(__file__).resolve().parent.parent
EVALUATION_DIR = ROOT / "group_project" / "evaluation"
DATASET_PATH = EVALUATION_DIR / "golden_dataset.json"
SAFETY_PATH = EVALUATION_DIR / "safety_cases.json"
METRICS = ("faithfulness", "answer_relevance", "context_recall", "context_precision")
CONFIGURATIONS = {"dense": "A · Dense only", "hybrid": "B · Hybrid + RRF"}


def load_dataset(path: Path = DATASET_PATH, *, verify_sources: bool = True) -> list[dict]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("Golden dataset must be a non-empty list")
    ids = set()
    corpus = {item["id"]: item for item in map(json.loads, CHUNKS_PATH.read_text(
        encoding="utf-8").splitlines())} if verify_sources else {}
    for case in cases:
        if any(not isinstance(case.get(key), str) or not case[key].strip()
               for key in ("id", "question", "expected_answer", "category")):
            raise ValueError("Golden case is missing a required text field")
        if case["id"] in ids:
            raise ValueError("Golden case IDs must be unique")
        ids.add(case["id"])
        contexts, sources = case.get("expected_context"), case.get("source_ids")
        if (not isinstance(contexts, list) or not contexts or not isinstance(sources, list)
                or len(contexts) != len(sources)):
            raise ValueError("Each expected context needs a source ID")
        for text, source_id in zip(contexts, sources):
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Expected contexts must be non-empty text")
            if verify_sources and (source_id not in corpus or generation._normalize_quote(text)
                    not in generation._normalize_quote(corpus[source_id]["content"])):
                raise ValueError(f"Golden source missing or changed: {source_id}")
    return cases


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".tmp",
                                     dir=path.parent, delete=False) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
        temporary = Path(handle.name)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def summarize(rows: list[dict]) -> dict:
    summary = {}
    for configuration in CONFIGURATIONS:
        selected = [row for row in rows if row["configuration"] == configuration and row["kind"] == "golden"]
        safety = [row for row in rows if row["configuration"] == configuration and row["kind"] == "safety"]
        scores, coverage = {}, {}
        for metric in METRICS:
            values = [row["metrics"][metric] for row in selected if row["metrics"].get(metric) is not None]
            scores[metric] = statistics.mean(values) if values else None
            coverage[metric] = len(values)
        summary[configuration] = {"scores": scores, "coverage": coverage, "cases": len(selected),
            "refusals": sum(row["run"]["result"]["retrieval_source"] == "none" for row in selected),
            "generation_errors": sum(row["run"]["generation"]["status"] == "error" for row in selected),
            "metric_errors": sum(len(row["metric_errors"]) for row in selected),
            "expected_source_hit_rate": statistics.mean([row["expected_source_hit"] for row in selected]) if selected else None,
            "mean_latency_ms": statistics.mean([row["run"]["elapsed_ms"] for row in selected]) if selected else None,
            "safety_passed": sum(row["safety_passed"] for row in safety), "safety_cases": len(safety)}
    return summary


def _display(value) -> str:
    return "N/A" if value is None else f"{value:.3f}"


def write_report(document: dict, path: Path) -> None:
    summary = document["summary"]
    config = document["settings"]
    lines = ["# Vietnam Travel RAG — Evaluation", "", f"Run: {document['created_at']}", "",
        "## Overall Scores", "", "Measured with RAGAS 0.4.3; higher is better. N/A is not counted as zero.", "",
        "| Configuration | Faithfulness | Answer relevance | Context recall | Context precision |",
        "| --- | ---: | ---: | ---: | ---: |"]
    for mode, title in CONFIGURATIONS.items():
        lines.append(f"| {title} | " + " | ".join(_display(summary[mode]["scores"][key]) for key in METRICS) + " |")
    lines += ["", "## A/B Comparison", "", "Only retrieval fusion changes. Both configurations use the same corpus, questions,",
        "top-k, fallback threshold, generation model/prompt, context reordering, and RAGAS judge.", "",
        f"- Top-k: {config['top_k']}; cosine threshold: {config['threshold']}; RRF k: 60.",
        f"- Generator: `{config['provider']}/{config['model']}`; temperature: {generation.TEMPERATURE}.",
        f"- Judge: `{config['judge_model']}`; relevance embeddings: `{config['judge_embedding_model']}`.",
        f"- Retrieval embeddings: `{config['embedding_provider']}/{config['embedding_model']}`.",
        f"- PageIndex configured: {config['pageindex_configured']}. Low-confidence queries keep local results if fallback is unavailable.",
        f"- Dataset SHA-256: `{config['dataset_sha256']}`.",
        f"- Corpus SHA-256: `{config['corpus_sha256']}`.", "",
        "| Metric | B minus A | A scored cases | B scored cases |", "| --- | ---: | ---: | ---: |"]
    for metric in METRICS:
        a, b = (summary[mode]["scores"][metric] for mode in CONFIGURATIONS)
        delta = b - a if a is not None and b is not None else None
        lines.append(f"| {metric} | {_display(delta)} | {summary['dense']['coverage'][metric]} | {summary['hybrid']['coverage'][metric]} |")
    for mode, title in CONFIGURATIONS.items():
        stats = summary[mode]
        lines += ["", f"{title}: {stats['cases']} golden cases; {stats['refusals']} refusals; "
            f"{stats['generation_errors']} generation errors; {stats['metric_errors']} metric errors. "
            f"Expected-source hit rate: {_display(stats['expected_source_hit_rate'])}. "
            f"Mean retrieval + generation time: {_display((stats['mean_latency_ms'] or 0) / 1000)} s. "
            f"Safety checks: {stats['safety_passed']}/{stats['safety_cases']}."]
    lines += ["", "## Worst Performers", "", "Sorted by the mean of available metrics; inspect each answer and context in `results.json`.", "",
        "| Case | Configuration | Mean | Diagnosis |", "| --- | --- | ---: | --- |"]
    def mean_score(row):
        values = [value for value in row["metrics"].values() if value is not None]
        return statistics.mean(values) if values else -1
    worst = sorted((row for row in document["rows"] if row["kind"] == "golden"), key=mean_score)[:6]
    for row in worst:
        diagnosis = ("Generation failed; inspect error type" if row["run"]["generation"]["status"] == "error" else
                     "Expected source missing from retrieved context" if not row["expected_source_hit"] else
                     "Source retrieved, but generation declined to answer" if row["run"]["result"]["retrieval_source"] == "none" else
                     "Source retrieved; review answer completeness and ordering of distractors")
        lines.append(f"| {row['case_id']} | {row['configuration']} | {mean_score(row):.3f} | {diagnosis} |")
    lines += ["", "## Recommendations", "",
        "- Inspect the lowest-scoring cases before adjusting retrieval; use source-hit diagnostics to separate retrieval from generation errors.",
        "- Repair the Saigon/Hanoi title-body mismatch in article_01 before expanding destination questions.",
        "- Replace archived visa guidance with verified current sources before using answers for travel decisions.",
        "- Add harder multi-section questions and a held-out set; repeat runs to estimate model/judge variation before declaring an A/B winner.",
        "- Calibrate the fallback threshold on a separate development set and verify PageIndex with a configured key.", "",
        "## Method and limitations", "",
        "The 15 manually authored, synthetic end-user questions cover all eight documents; they are not collected user logs. Questions omit document titles and section hints and include practical travel situations. Expected context is copied from stable corpus chunk IDs and validated before evaluation.",
        "The two safety questions are scored separately by refusal behavior; they are excluded from the four RAGAS aggregates.",
        "All retrieved chunks passed to generation are evaluated, not just the final cited sources. Context precision therefore includes distractors.",
        "Faithfulness is not applicable for refusals (reported N/A); refusal counts and metric coverage prevent this exclusion from hiding failures.",
        "Answer relevance is RAGAS question-reconstruction similarity; recall and precision use the reference answer. No custom proxy is labelled as a RAGAS metric.",
        "Metric failures remain null with exception types. A safety refusal caused by a provider error is not counted as a successful safety check.",
        "This is a small development benchmark with one sample per configuration/question, not a significance test. The same model family generates and judges answers, so judge bias is possible.",
        "Timing excludes RAGAS scoring and can include cache warm-up/network variation; it is not a controlled latency benchmark.",
        "Citation IDs/quotes are mechanically checked by generation, but semantic support remains subject to model and judge error.", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


async def _score_run(run, scorers, metric_slots, reference=None, on_progress=None):
    """Judge this exact answer and all its retrieved context, without regenerating it."""
    common = {"user_input": run["query"]}
    response = re.sub(r"\[\d+\]", "", run["result"]["answer"]).strip()
    contexts = [item["content"] for item in run["retrieval"]["results"]]
    jobs = {"answer_relevance": {**common, "response": response}}
    if run["result"]["sources"]:
        jobs["faithfulness"] = {**common, "response": response, "retrieved_contexts": contexts}
    if reference is not None:
        for metric in ("context_recall", "context_precision"):
            jobs[metric] = {**common, "retrieved_contexts": contexts, "reference": reference}
    metrics, errors = dict.fromkeys(METRICS), {}
    done = 0

    async def score(metric, kwargs):
        nonlocal done
        async with metric_slots:
            try:
                result = await asyncio.wait_for(scorers[metric].ascore(**kwargs), timeout=120)
                value = float(result.value)
                if not math.isfinite(value) or not 0 <= value <= 1:
                    raise ValueError("Invalid metric value")
                metrics[metric] = value
            except Exception as exc:
                errors[metric] = type(exc).__name__
            done += 1
            if on_progress:
                on_progress(done, len(jobs), metric)

    await asyncio.gather(*(score(key, kwargs) for key, kwargs in jobs.items()))
    return {"metrics": metrics, "metric_errors": errors}


def evaluate_answer(run, reference=None, on_progress=None):
    """Score one displayed answer. Custom questions have no reference-based scores."""
    async def evaluate():
        os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
        from openai import AsyncOpenAI
        from ragas.embeddings import OpenAIEmbeddings
        from ragas.llms import llm_factory
        from ragas.metrics.collections import Faithfulness, AnswerRelevancy, ContextRecall, ContextPrecision

        if not os.getenv("OPENAI_API_KEY", "").strip():
            raise RuntimeError("Evaluation requires OPENAI_API_KEY")
        model = os.getenv("EVAL_MODEL", "").strip() or "gpt-4.1-mini"
        async with AsyncOpenAI(timeout=60, max_retries=0) as client:
            llm = llm_factory(model, client=client, temperature=0, max_tokens=2048, max_retries=1)
            embeddings = OpenAIEmbeddings(client=client, model="text-embedding-3-small")
            scorers = {"faithfulness": Faithfulness(llm=llm),
                "answer_relevance": AnswerRelevancy(llm=llm, embeddings=embeddings),
                "context_recall": ContextRecall(llm=llm), "context_precision": ContextPrecision(llm=llm)}
            result = await _score_run(run, scorers, asyncio.Semaphore(4), reference, on_progress)
            return {**result, "judge_model": model, "scored_at": datetime.now(timezone.utc).isoformat()}
    return asyncio.run(evaluate())


async def _evaluate(cases, safety, output, top_k, threshold, progress, resume):
    os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
    from openai import AsyncOpenAI
    from ragas.embeddings import OpenAIEmbeddings
    from ragas.llms import llm_factory
    from ragas.metrics.collections import Faithfulness, AnswerRelevancy, ContextRecall, ContextPrecision

    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise RuntimeError("Evaluation requires OPENAI_API_KEY for the RAGAS judge")
    from .task8_pageindex_vectorless import PAGEINDEX_API_KEY
    settings = {"top_k": top_k, "threshold": threshold, "provider": generation.LLM_PROVIDER,
        "model": generation.LLM_MODEL or generation.DEFAULT_MODELS.get(generation.LLM_PROVIDER, ""),
        "judge_model": os.getenv("EVAL_MODEL", "").strip() or "gpt-4.1-mini",
        "judge_embedding_model": "text-embedding-3-small", "ragas_version": "0.4.3",
        "embedding_provider": EMBEDDING_PROVIDER, "embedding_model": EMBEDDING_MODEL,
        "pageindex_configured": bool(PAGEINDEX_API_KEY),
        "dataset_sha256": hashlib.sha256(json.dumps(cases + safety, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        "corpus_sha256": hashlib.sha256(CHUNKS_PATH.read_bytes()).hexdigest(),
        "pipeline_sha256": hashlib.sha256(b"".join(path.read_bytes() for path in sorted((ROOT / "src").glob("*.py")))).hexdigest()}
    document = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "running", "settings": settings, "rows": [], "summary": {}}
    result_path = output / "results.json"
    if resume and result_path.exists():
        previous = json.loads(result_path.read_text(encoding="utf-8"))
        if previous.get("settings") == settings:
            document = previous
            document["status"] = "running"
    completed = {(row["case_id"], row["configuration"]) for row in document["rows"]}
    total = 2 * (len(cases) + len(safety))
    metric_slots = asyncio.Semaphore(4)
    case_slots = asyncio.Semaphore(2)

    async with AsyncOpenAI(timeout=60, max_retries=0) as client:
        llm = llm_factory(settings["judge_model"], client=client, temperature=0, max_tokens=2048, max_retries=1)
        embeddings = OpenAIEmbeddings(client=client, model=settings["judge_embedding_model"])
        scorers = {"faithfulness": Faithfulness(llm=llm),
            "answer_relevance": AnswerRelevancy(llm=llm, embeddings=embeddings),
            "context_recall": ContextRecall(llm=llm), "context_precision": ContextPrecision(llm=llm)}

        async def one(case, mode, kind):
            if (case["id"], mode) in completed:
                return
            async with case_slots:
                run = await asyncio.to_thread(run_question, case["question"], top_k, threshold, mode == "hybrid")
                row = {"case_id": case["id"], "configuration": mode, "kind": kind,
                    "question": case["question"], "reference": case.get("expected_answer"),
                    "run": run, "metrics": {key: None for key in METRICS}, "metric_errors": {}}
                if kind == "safety":
                    row["safety_passed"] = (run["generation"]["status"] == "no_evidence"
                                            and run["result"]["retrieval_source"] == "none")
                else:
                    retrieved = run["retrieval"]["results"]
                    row["expected_source_hit"] = bool(set(case["source_ids"]) & {item["id"] for item in retrieved})
                    row.update(await _score_run(run, scorers, metric_slots, case["expected_answer"]))
                document["rows"].append(row)
                document["rows"].sort(key=lambda row: (row["case_id"], row["configuration"]))
                document["summary"] = summarize(document["rows"])
                write_json(result_path, document)
                if progress:
                    progress(len(document["rows"]), total, f"{case['id']} · {mode}")

        await asyncio.gather(*(one(case, mode, kind)
            for kind, dataset in (("golden", cases), ("safety", safety))
            for case in dataset for mode in CONFIGURATIONS))
    document["status"] = "complete"
    document["summary"] = summarize(document["rows"])
    write_json(result_path, document)
    write_report(document, output / "RESULT.md")
    return document


def run_evaluation(output: Path = EVALUATION_DIR, top_k: int = 5,
                   threshold: float = SCORE_THRESHOLD, limit: int | None = None,
                   progress=None, resume: bool = True) -> dict:
    if type(top_k) is not int or top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    if not isinstance(threshold, (float, int)) or not math.isfinite(threshold) or not -1 <= threshold <= 1:
        raise ValueError("threshold must be a cosine value in [-1, 1]")
    if limit is not None and (type(limit) is not int or limit <= 0):
        raise ValueError("limit must be positive")
    cases = load_dataset()
    safety = json.loads(SAFETY_PATH.read_text(encoding="utf-8")) if limit is None else []
    if limit:
        cases = cases[:limit]
    return asyncio.run(_evaluate(cases, safety, Path(output), top_k, threshold, progress, resume))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=EVALUATION_DIR)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=SCORE_THRESHOLD)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()
    run_evaluation(args.output, args.top_k, args.threshold, args.limit,
        progress=lambda done, total, label: print(f"[{done}/{total}] {label}", flush=True), resume=not args.fresh)
    print(f"Results: {args.output / 'RESULT.md'}")
