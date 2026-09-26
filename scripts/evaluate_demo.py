"""Evaluate unchanged task10 with the configured OpenAI key and task11 rubric.

Run from the repository root: python -m scripts.evaluate_demo [--fresh]
The original Gemini results are preserved. This is a custom LLM judge, not RAGAS.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import time
import unicodedata

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

from src import task10_generation as generation
from src.task11_evaluation import JUDGE_PROMPT, METRICS

OUTPUT = ROOT / "reports" / "demo_eval_results.json"
REPORT = ROOT / "reports" / "DEMO_RESULT.md"
DATASET = ROOT / "group_project" / "evaluation" / "golden_dataset.json"


def save(document):
    for row in document["cases"]:
        normalized = unicodedata.normalize("NFC", row["answer"]).strip().casefold()
        row["refused"] = (generation.SAFE_REFUSAL.rstrip('.').casefold() in normalized
                          or normalized.startswith(("tôi không thể xác minh", "i cannot verify")))
    for name in ("A_dense_only", "B_hybrid_rrf"):
        rows = [row for row in document["cases"] if row["config"] == name]
        scores = {metric: statistics.mean(row[metric] for row in rows) if rows else None for metric in METRICS}
        scores["average"] = statistics.mean(scores.values()) if rows else None
        document["scores"][name] = scores
    document["completed_config_case_runs"] = len(document["cases"])
    document["delta_B_minus_A"] = {
        metric: document["scores"]["B_hybrid_rrf"][metric] - document["scores"]["A_dense_only"][metric]
        if all(document["scores"][name][metric] is not None for name in document["scores"]) else None
        for metric in (*METRICS, "average")
    }
    temporary = OUTPUT.with_suffix('.tmp')
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(OUTPUT)


def write_report(document):
    lines = ["# Demo evaluation", "", f"Run: {document['run_at_utc']}; status: {document['status']}.", "",
        f"15 questions, two retrieval configurations, top_k={document['top_k']}; 540 indexed chunks.",
        f"Generator: `{document['generator_model']}`; judge: `{document['evaluator_model']}` (OpenAI).",
        f"Embedding: `{document['embedding_model']}`, 3072 dimensions.",
        "The unchanged task10 generation pipeline and task11 scoring rubric are used. This is a custom LLM judge, not RAGAS.", "",
        "## Overall scores", "", "| Metric | Dense only | Hybrid + RRF | B minus A |", "| --- | ---: | ---: | ---: |"]
    for metric in (*METRICS, "average"):
        a, b = (document['scores'][name][metric] for name in ('A_dense_only', 'B_hybrid_rrf'))
        lines.append(f"| {metric} | {a:.3f} | {b:.3f} | {b-a:+.3f} |")
    lines += ["", "## A/B comparison", "",
        "Both arms use the same corpus, questions, generation prompt/model, judge, top-k, and context reorder. PageIndex is disabled with threshold -1.0 for both arms.",
        "Task9 still calls BM25 in dense-only mode but returns dense results without fusion; its implementation is unchanged."]
    for name in ('A_dense_only', 'B_hybrid_rrf'):
        rows = [row for row in document['cases'] if row['config'] == name]
        lines.append(f"- {name}: {len(rows)} cases; {sum(row['refused'] for row in rows)} refusals; mean retrieval + generation {statistics.mean(row['latency_ms'] for row in rows)/1000:.2f} s.")
    lines += ["", "## Worst performers", "", "These diagnoses are the judge's notes and require manual review.", "",
        "| Case | Configuration | Mean | Judge notes |", "| --- | --- | ---: | --- |"]
    for row in sorted(document['cases'], key=lambda row: statistics.mean(row[m] for m in METRICS))[:3]:
        notes = row['notes'].replace('|', '/').replace('\n', ' ')
        lines.append(f"| {row['case']} | {row['config']} | {statistics.mean(row[m] for m in METRICS):.3f} | {notes} |")
    lines += ["", "## Recommendations", "",
        "- Review the cited chunks and judge notes for the lowest-scoring cases before changing retrieval.",
        "- Repeat on a held-out dataset before selecting a retrieval configuration; this is one run on 15 development questions.",
        "- Validate citations manually. The same model generates and judges responses, so scores can be biased.",
        "- Refresh archived visa sources and resolve the article title/body mismatch before treating answers as current travel guidance.",
        "", "Raw answers, retrieved IDs, metric scores, judge notes and latency are saved in `demo_eval_results.json`. Latency excludes judging; costs are not measured.", ""]
    REPORT.write_text('\n'.join(lines), encoding='utf-8')


def run(fresh=False):
    if generation.LLM_PROVIDER.lower() != 'openai':
        raise ValueError('This adapter requires LLM_PROVIDER=openai')
    cases = json.loads(DATASET.read_text(encoding='utf-8'))
    model = os.getenv('EVALUATOR_MODEL') or generation.LLM_MODEL or 'gpt-4o-mini'
    digest = hashlib.sha256(DATASET.read_bytes() + b''.join(
        p.read_bytes() for p in sorted((ROOT / 'data' / 'standardized').rglob('*.md'))
    ) + b''.join(p.read_bytes() for p in sorted((ROOT / 'src').glob('task*.py')))).hexdigest()
    settings = {'dataset_corpus_pipeline_sha256': digest, 'top_k': 5,
        'generator_model': generation.LLM_MODEL or 'gpt-4o-mini', 'evaluator_model': model,
        'embedding_model': os.getenv('EMBEDDING_MODEL'), 'generator_provider': 'openai',
        'evaluator_provider': 'openai', 'evaluation_method': 'OpenAI LLM judge'}
    document = {**settings, 'run_at_utc': datetime.now(timezone.utc).isoformat(),
        'dataset_size': len(cases), 'status': 'running', 'scores': {}, 'cases': [], 'blocked_by': None}
    if OUTPUT.exists() and not fresh:
        previous = json.loads(OUTPUT.read_text(encoding='utf-8'))
        if all(previous.get(key) == value for key, value in settings.items()):
            document = previous
            document.update(status='running', blocked_by=None)
    done = {(row['case'], row['config']) for row in document['cases']}
    schema = {'type': 'object', 'properties': {
        **{metric: {'type': 'number'} for metric in METRICS}, 'notes': {'type': 'string'}},
        'required': [*METRICS, 'notes'], 'additionalProperties': False}
    with OpenAI(timeout=60, max_retries=1) as client:
        for index, case in enumerate(cases, 1):
            for name, rerank in (('A_dense_only', False), ('B_hybrid_rrf', True)):
                if (index, name) in done:
                    continue
                print(f"[{len(document['cases'])+1}/{2*len(cases)}] case {index} {name}: generating", flush=True)
                started = time.perf_counter()
                try:
                    generated = generation.generate_for_config(case['question'], top_k=5,
                        use_reranking=rerank, score_threshold=-1.0)
                    latency = round((time.perf_counter() - started)*1000, 2)
                    if not generated['sources']:
                        raise RuntimeError('Generation returned no sources; verify retrieval before evaluating')
                    payload = {**case, 'answer': generated['answer'], 'retrieved_context': [
                        {'id': source['id'], 'title': source['metadata'].get('title'), 'content': source['content']}
                        for source in generated['sources']]}
                    response = client.chat.completions.create(model=model, temperature=0,
                        messages=[{'role': 'user', 'content': JUDGE_PROMPT.format(payload=json.dumps(payload, ensure_ascii=False))}],
                        response_format={'type': 'json_schema', 'json_schema': {'name': 'rag_scores', 'strict': True, 'schema': schema}})
                    if response.choices[0].finish_reason != 'stop':
                        raise ValueError('Judge response incomplete')
                    scores = json.loads(response.choices[0].message.content)
                    for metric in METRICS:
                        value = scores[metric]
                        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                            raise ValueError(f'Invalid metric: {metric}')
                    document['cases'].append({'case': index, 'question': case['question'], 'config': name,
                        'answer': generated['answer'], 'retrieved_ids': [s['id'] for s in generated['sources']],
                        'latency_ms': latency, 'refused': generation.SAFE_REFUSAL.rstrip('.') in generated['answer'], **scores})
                    save(document)
                    print(f"  saved; average={statistics.mean(scores[m] for m in METRICS):.3f}", flush=True)
                except Exception as exc:
                    document.update(status='partial', blocked_by=type(exc).__name__)
                    save(document)
                    raise RuntimeError(f'Case {index}/{name} stopped: {type(exc).__name__}; saved checkpoint') from None
    document['status'] = 'complete'
    save(document)
    write_report(document)
    print(json.dumps({'status': document['status'], 'runs': len(document['cases']), 'scores': document['scores']}, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fresh', action='store_true')
    run(parser.parse_args().fresh)
