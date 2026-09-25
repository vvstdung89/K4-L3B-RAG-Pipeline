# Vietnam Travel RAG — Evaluation

Run: 2026-09-25T05:49:55.064724+00:00. Status: complete. 15 golden questions × 2 configurations, plus 2 safety questions × 2 configurations. Scores below are copied from `results.json`; missing metric values stay null and are not treated as zero.

## Overall Scores

Measured with RAGAS 0.4.3; higher is better. N/A is not counted as zero.

| Configuration | Faithfulness | Answer relevance | Context recall | Context precision |
| --- | ---: | ---: | ---: | ---: |
| A · Dense only | 1.000 | 0.562 | 0.967 | 0.845 |
| B · Hybrid + RRF | 1.000 | 0.660 | 0.900 | 0.745 |

Coverage: faithfulness 12/15 vs 14/15; answer relevance 14/15 vs 15/15; context recall 15/15 vs 15/15; context precision 15/15 vs 14/15. The four missing faithfulness scores are safe refusals, not unfaithful answers.

## A/B Comparison

Only retrieval fusion changes. Both configurations use the same corpus, questions, top-k, fallback threshold, generation model/prompt, context reordering, and RAGAS judge.

- Top-k: 5; cosine threshold: 0.5; RRF k: 60.
- Generator: `openai/gpt-4.1-mini`; temperature: 0.3.
- Judge: `gpt-4.1-mini`; relevance embeddings: `text-embedding-3-small`.
- Retrieval embeddings: `openai/text-embedding-3-small`.
- PageIndex configured: False. Low-confidence queries keep local results if fallback is unavailable.
- Dataset SHA-256: `3a118dd47f9f18a5d946abdfdb4b0c20a8edb58b2fdb88b72c35d4002b7c2e34`.
- Corpus SHA-256: `45f1a98470f51a3939a438140afb6a337fb32c01069d4cf2532692dde8855ffa`.
- Pipeline SHA-256: `78516daaa437e3e6feaa87987e910a946814341a637f1550f9bd5ca318534386`.

| Metric | B minus A | A scored cases | B scored cases |
| --- | ---: | ---: | ---: |
| faithfulness | 0.000 | 12 | 14 |
| answer_relevance | 0.097 | 14 | 15 |
| context_recall | -0.067 | 15 | 15 |
| context_precision | -0.100 | 15 | 14 |

A · Dense only: 15 golden cases; 3 refusals; 3 generation errors; 1 metric error. Expected-source hit rate: 0.933 (14/15). Mean retrieval + generation time: 2.674 s. Safety checks: 2/2.

B · Hybrid + RRF: 15 golden cases; 1 refusal; 1 generation error; 1 metric error. Expected-source hit rate: 0.800 (12/15). Mean retrieval + generation time: 2.511 s. Safety checks: 2/2.

Hybrid is not an overall winner on this single sample. It raises answer relevance by 0.097 and turns two dense generation failures (Q09, Q12) into cited answers, with slightly lower mean latency. It lowers context recall by 0.067, context precision by 0.100, and expected-source hit rate from 0.933 to 0.800. On the 12 questions both configurations completed, the relevance gap shrinks to +0.019 while recall and precision still favor dense (−0.083 and −0.082). Faithfulness is 1.000 on every grounded answer in both configurations.

`result.retrieval_source` is `hybrid` for every cited answer, including dense-only runs, because generation uses that label for any non-PageIndex citation. The ablation flag is `retrieval.use_reranking`, not that field. Dense-only did not run BM25 or RRF.

Safety is separate from the four aggregates. S01 (pizza recipe) and S02 (tomorrow's Hanoi–Tokyo fare) returned the fixed refusal in both configurations, with `generation.status = no_evidence` and no citations. Retrieved chunks were present but unused.

## Worst Performers

Sorted by the mean of available metrics. Retrieval hits are checked against the golden chunk ID, not against whether another chunk happened to contain the same fact.

| Case | Configuration | Mean | Faithfulness | Relevance | Recall | Precision | Failure stage | Diagnosis |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Q12 | dense | 0.417 | N/A | 0.000 | 1.000 | 0.250 | generation | Expected `article_03.md::chunk-2` was retrieved, then generation raised `ValueError` and refused. Hybrid cited that chunk and listed chả mực, sá sùng, hàu nướng, chả rươi, and sam biển. |
| Q14 | dense | 0.583 | N/A | 0.000 | 1.000 | 0.750 | generation | Expected `article_05.md::chunk-1` was retrieved. Generation raised `ValueError` and refused. The exception message is not stored. |
| Q05 | hybrid | 0.600 | 1.000 | 0.398 | 0.000 | 1.000 | retrieval | Expected `LUẬT DU LỊCH.md::chunk-2` was missing. The answer defined domestic tourists and omitted the paid-work exclusion. Dense had ranked that chunk 3rd and cited it. |
| Q14 | hybrid | 0.667 | N/A | 0.000 | 1.000 | 1.000 | generation | Same expected beach chunk was retrieved and the same `ValueError` refusal occurred. This is not a fusion miss. |
| Q09 | dense | 0.667 | N/A | 0.000 | 1.000 | 1.000 | generation | Expected `article_02.md::chunk-1` was retrieved, but generation refused. Hybrid cited it and returned 135 Nam Ky Khoi Nghia. |
| Q07 | dense | 0.694 | 1.000 | 0.275 | 0.500 | 1.000 | retrieval | Expected definition `LUẬT DU LỊCH.md::chunk-7` was missing in both configurations. The answer used later community-tourism articles, so it is grounded but does not state that the community manages, organizes, and benefits. |

Other measured misses that are not in the lowest-six list:

- Q03 hybrid did not retrieve `vietnam_visitors_notes.md::chunk-2`, so the source hit is false, but context recall is 1.000. It cited the six-month validity rule from the visa document instead of the "entry may be refused" sentence. Dense cited the expected note.
- Q07 hybrid has the same missing definition chunk and the same 0.500 recall / 0.285 relevance pattern as dense.
- Q04 hybrid context precision and Q05 dense answer relevance are null because the judge raised `InstructorRetryException`. Those cells are excluded from the means.
- Q06 and Q15 have the expected source, recall 1.000, and a correct citation, but answer relevance is only 0.339–0.506. That is a short-answer reconstruction penalty, not a retrieval failure.

## Recommendations

- Do not change the default to hybrid from this run alone. Hybrid helps generation succeed more often here, but dense finds the expected chunk more often. Repeat the 15-question run before calling a winner.
- Inspect Q05 fusion before changing `k` or top-k. Dense already placed the tourist-definition chunk in the top 5; RRF replaced it with other law chunks and the answer became a different definition.
- Treat Q07 as a ranking/chunking problem in both configurations. The community-tourism definition is losing to later articles on the same topic. A heading-aware or definition-level chunk would be a more direct fix than another fusion pass.
- Persist the generation `ValueError` message, not the provider body, and rerun Q09, Q12, and Q14. All four failures happened after the expected chunk was already in context, so retrieval changes will not explain them.
- Rescore the two `InstructorRetryException` cells before comparing Q04 precision or Q05 dense relevance.
- Do not tune retrieval to chase Q06/Q15 answer relevance. Those answers already cite the expected fact.
- Keep the archived visa documents labeled as historical corpus, not current entry advice. Repair the Saigon/Hanoi title-body mismatch in `article_01` before adding destination questions.
- PageIndex was not configured, so fallback was not measured. Calibrate the 0.5 cosine threshold on a held-out set before treating it as a safety boundary.

## Method and limitations

The 15 manually authored, synthetic end-user questions cover all eight documents; they are not collected user logs. Questions omit document titles and section hints and include practical travel situations. Expected context is copied from stable corpus chunk IDs and validated before evaluation.
The two safety questions are scored separately by refusal behavior; they are excluded from the four RAGAS aggregates.
All retrieved chunks passed to generation are evaluated, not just the final cited sources. Context precision therefore includes distractors.
Faithfulness is not applicable for refusals (reported N/A); refusal counts and metric coverage prevent this exclusion from hiding failures.
Answer relevance is RAGAS question-reconstruction similarity; recall and precision use the reference answer. No custom proxy is labelled as a RAGAS metric.
Metric failures remain null with exception types. A safety refusal caused by a provider error is not counted as a successful safety check.
This is a small development benchmark with one sample per configuration/question, not a significance test. The same model family generates and judges answers, so judge bias is possible.
Timing excludes RAGAS scoring and can include cache warm-up/network variation; it is not a controlled latency benchmark.
Citation IDs/quotes are mechanically checked by generation, but semantic support remains subject to model and judge error. Generation stores only the exception class, so the four `ValueError` refusals cannot be split into schema, quote-mismatch, or provider-completion failures from this file alone.

## Verification

Offline submission checks were run in this workspace after the pipeline code used for this evaluation was in place:

| Command | Result |
| --- | --- |
| `pytest tests/test_contracts.py -q` | 15 passed |
| `pytest tests/test_acceptance.py -q` | 5 passed |
| `pytest -q` | 138 passed |

These checks validate contracts, corpus files, the golden dataset, and this report's required sections. They do not replace the RAGAS scores above.
