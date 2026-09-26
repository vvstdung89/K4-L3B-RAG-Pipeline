# Demo evaluation

Run: 2026-09-26T02:49:37.336014+00:00; status: complete.

15 questions, two retrieval configurations, top_k=5; 540 indexed chunks.
Generator: `gpt-4o-mini`; judge: `gpt-4o-mini` (OpenAI).
Embedding: `text-embedding-3-large`, 3072 dimensions.
The unchanged task10 generation pipeline and task11 scoring rubric are used. This is a custom LLM judge, not RAGAS.

## Overall scores

| Metric | Dense only | Hybrid + RRF | B minus A |
| --- | ---: | ---: | ---: |
| faithfulness | 0.933 | 0.867 | -0.067 |
| answer_relevance | 0.933 | 0.867 | -0.067 |
| context_recall | 0.933 | 0.867 | -0.067 |
| context_precision | 0.933 | 0.833 | -0.100 |
| average | 0.933 | 0.858 | -0.075 |

## A/B comparison

Both arms use the same corpus, questions, generation prompt/model, judge, top-k, and context reorder. PageIndex is disabled with threshold -1.0 for both arms.
Task9 still calls BM25 in dense-only mode but returns dense results without fusion; its implementation is unchanged.
- A_dense_only: 15 cases; 0 refusals; mean retrieval + generation 1.98 s.
- B_hybrid_rrf: 15 cases; 0 refusals; mean retrieval + generation 1.65 s.

## Worst performers

These diagnoses are the judge's notes and require manual review.

| Case | Configuration | Mean | Judge notes |
| --- | --- | ---: | --- |
| 2 | A_dense_only | 0.000 | Missing definition of ecological tourism; failure stage: retrieval. |
| 11 | B_hybrid_rrf | 0.000 | Missing evidence about ticket price and details; failure stage: retrieval. |
| 5 | B_hybrid_rrf | 0.500 | Missing evidence for Thai passport; failure in retrieval. |

## Recommendations

- Review the cited chunks and judge notes for the lowest-scoring cases before changing retrieval.
- Repeat on a held-out dataset before selecting a retrieval configuration; this is one run on 15 development questions.
- Validate citations manually. The same model generates and judges responses, so scores can be biased.
- Refresh archived visa sources and resolve the article title/body mismatch before treating answers as current travel guidance.

Raw answers, retrieved IDs, metric scores, judge notes and latency are saved in `demo_eval_results.json`. Latency excludes judging; costs are not measured.
