import React, { useState } from 'react';
import { api, EvalMetrics, EvalRow, fmtMs, fmtScore, useApi } from '../api';
import { AnswerText, Card, CardTitle, Empty, ErrorBox, Kpi, Loading } from '../components/ui';

const METRICS: { key: keyof EvalMetrics & keyof EvalRow; label: string }[] = [
  { key: 'faithfulness', label: 'Faithfulness' },
  { key: 'answer_relevancy', label: 'Answer relevancy' },
  { key: 'context_recall', label: 'Context recall' },
  { key: 'context_precision', label: 'Context precision' },
];

const CONFIG_LABEL: Record<string, string> = {
  A_dense: 'A · Dense only',
  B_hybrid_rrf: 'B · Hybrid BM25 + RRF',
};

const rowAverage = (row: EvalRow) => {
  const values = METRICS.map((m) => row[m.key] as number | null).filter((v): v is number => v !== null);
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
};

const Delta: React.FC<{ a: number | null; b: number | null; digits?: number; invert?: boolean }> = ({ a, b, digits = 4, invert }) => {
  if (a === null || b === null) return <span>—</span>;
  const diff = b - a;
  const good = invert ? diff < 0 : diff > 0;
  return (
    <span className={`font-mono font-semibold ${diff === 0 ? 'text-on-surface-variant' : good ? 'text-secondary' : 'text-error'}`}>
      {diff > 0 ? '+' : ''}
      {diff.toFixed(digits)}
    </span>
  );
};

export const EvaluationView: React.FC = () => {
  const evaluation = useApi('evaluation', api.evaluation);
  const [runName, setRunName] = useState<string | null>(null);
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  if (evaluation.loading) return <Loading />;
  if (evaluation.error) return <ErrorBox error={evaluation.error} onRetry={evaluation.reload} />;
  const { summary, runs, golden } = evaluation.data!;
  if (!summary) {
    return (
      <Card className="p-space-xl">
        <Empty icon="science">
          Chưa có kết quả đánh giá. Chạy <code className="font-mono">python -m group_project.evaluation.run_evaluation</code>.
        </Empty>
      </Card>
    );
  }

  const names = Object.keys(summary.configs);
  const [nameA, nameB] = names;
  const A = summary.configs[nameA];
  const B = nameB ? summary.configs[nameB] : null;
  const currentRun = runName ?? nameB ?? nameA;
  const rows = (runs[currentRun] ?? [])
    .map((row, index) => ({ row, index, avg: rowAverage(row) }))
    .sort((x, y) => (x.avg ?? -1) - (y.avg ?? -1));
  const winner = B && A.average !== null && B.average !== null ? (B.average >= A.average ? nameB : nameA) : null;
  const cal = summary.calibration;

  return (
    <div className="flex flex-col gap-space-lg pb-space-xl">
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-space-md">
        <Kpi label="Ngày đánh giá" icon="event" value={summary.evaluation_date} />
        <Kpi label="Golden set" icon="checklist" value={`${summary.golden_size} câu`} hint={`${golden.length} trong golden_dataset.json`} />
        <Kpi label="top_k" icon="filter_list" value={summary.top_k} />
        <Kpi label="Generator" icon="smart_toy" value={summary.generator.split('/').pop()} hint={summary.generator} />
        <Kpi label="Evaluator" icon="gavel" value={summary.evaluator} hint={summary.evaluator_embedding} />
        <Kpi label="Tốt hơn" icon="emoji_events" value={winner ? CONFIG_LABEL[winner]?.split(' · ')[0] ?? winner : '—'} hint={winner ? CONFIG_LABEL[winner] : undefined} />
      </div>

      <Card className="overflow-hidden">
        <div className="p-space-lg border-b border-slate-100">
          <CardTitle icon="compare_arrows" title="So sánh cấu hình A/B (RAGAS)" subtitle="group_project/evaluation/results/summary.json" />
        </div>
        <table className="w-full text-left font-body-md text-body-md">
          <thead>
            <tr className="bg-surface-container-low font-label-sm text-label-sm uppercase font-mono text-on-surface-variant">
              <th className="px-space-lg py-space-sm">Metric</th>
              {names.map((name) => (
                <th key={name} className="px-space-md py-space-sm">
                  {CONFIG_LABEL[name] ?? name}
                </th>
              ))}
              {B && <th className="px-space-md py-space-sm">Δ (B − A)</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {[...METRICS, { key: 'average' as const, label: 'Trung bình' }].map((metric) => (
              <tr key={metric.key} className={metric.key === 'average' ? 'bg-surface-container-low/60 font-semibold' : ''}>
                <td className="px-space-lg py-space-sm">{metric.label}</td>
                {names.map((name) => {
                  const value = summary.configs[name][metric.key] as number | null;
                  return (
                    <td key={name} className="px-space-md py-space-sm">
                      <div className="flex items-center gap-space-sm">
                        <span className="font-mono w-14">{fmtScore(value, 4)}</span>
                        <div className="flex-1 h-1.5 bg-surface-container rounded-full overflow-hidden max-w-[160px]">
                          <div className="h-full bg-secondary" style={{ width: `${(value ?? 0) * 100}%` }}></div>
                        </div>
                      </div>
                    </td>
                  );
                })}
                {B && (
                  <td className="px-space-md py-space-sm">
                    <Delta a={A[metric.key] as number | null} b={B[metric.key] as number | null} />
                  </td>
                )}
              </tr>
            ))}
            <tr>
              <td className="px-space-lg py-space-sm">Số lần từ chối</td>
              {names.map((name) => (
                <td key={name} className="px-space-md py-space-sm font-mono">{summary.configs[name].refusals}</td>
              ))}
              {B && <td className="px-space-md py-space-sm"><Delta a={A.refusals} b={B.refusals} digits={0} invert /></td>}
            </tr>
            <tr>
              <td className="px-space-lg py-space-sm">Source hit rate</td>
              {names.map((name) => (
                <td key={name} className="px-space-md py-space-sm font-mono">{(summary.configs[name].source_hit_rate * 100).toFixed(1)}%</td>
              ))}
              {B && <td className="px-space-md py-space-sm"><Delta a={A.source_hit_rate} b={B.source_hit_rate} /></td>}
            </tr>
            <tr>
              <td className="px-space-lg py-space-sm">Latency TB (retrieval)</td>
              {names.map((name) => (
                <td key={name} className="px-space-md py-space-sm font-mono">
                  {fmtMs(summary.configs[name].latency_ms_mean)} ({fmtMs(summary.configs[name].retrieval_ms_mean)})
                </td>
              ))}
              {B && <td className="px-space-md py-space-sm"><Delta a={A.latency_ms_mean} b={B.latency_ms_mean} digits={0} invert /></td>}
            </tr>
          </tbody>
        </table>
      </Card>

      {cal && (
        <Card className="p-space-lg flex flex-col gap-space-md">
          <CardTitle
            icon="tune"
            title="Hiệu chỉnh ngưỡng fallback (cosine top-1)"
            subtitle={`Ngưỡng cấu hình ${cal.configured_threshold} · ${cal.in_domain_below_threshold}/${summary.golden_size} câu in-domain nằm dưới ngưỡng`}
          />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-space-md">
            {(['in_domain', 'out_of_domain'] as const).map((key) => (
              <div key={key} className="bg-surface-container-low rounded-lg p-space-md">
                <div className="font-label-sm text-label-sm uppercase font-mono text-on-surface-variant">
                  {key === 'in_domain' ? 'Trong domain (golden set)' : 'Ngoài domain'}
                </div>
                <div className="font-mono font-body-md text-body-md text-primary mt-1">
                  min {cal[key].min} · mean {cal[key].mean} · max {cal[key].max}
                </div>
                <div className="relative h-3 mt-space-sm bg-surface-container rounded">
                  <div
                    className={`absolute inset-y-0 rounded ${key === 'in_domain' ? 'bg-secondary' : 'bg-tertiary-fixed-dim'}`}
                    style={{ left: `${cal[key].min * 100}%`, width: `${(cal[key].max - cal[key].min) * 100}%` }}
                  ></div>
                  <div className="absolute -inset-y-1 w-0.5 bg-error" style={{ left: `${cal.configured_threshold * 100}%` }}></div>
                </div>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-space-xs">
            {Object.entries(cal.out_of_domain_scores).map(([q, score]) => (
              <span key={q} className="px-space-sm py-1 rounded bg-surface-container-low font-label-sm text-label-sm">
                {q} · <span className="font-mono">{score}</span>
              </span>
            ))}
          </div>
        </Card>
      )}

      <Card className="overflow-hidden">
        <div className="p-space-lg border-b border-slate-100 flex flex-wrap items-center justify-between gap-space-sm">
          <CardTitle icon="bug_report" title="Chi tiết từng câu hỏi" subtitle="Sắp xếp từ điểm trung bình thấp nhất" />
          <div className="flex gap-space-xs bg-surface-container-low p-1 rounded-lg">
            {names.map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => {
                  setRunName(name);
                  setOpenIndex(null);
                }}
                className={`px-space-md py-1 rounded font-body-sm text-body-sm cursor-pointer ${
                  currentRun === name ? 'bg-surface-container-lowest text-primary shadow-sm font-semibold' : 'text-on-surface-variant'
                }`}
              >
                {CONFIG_LABEL[name] ?? name}
              </button>
            ))}
          </div>
        </div>
        <div className="divide-y divide-slate-100">
          {rows.map(({ row, index, avg }) => (
            <div key={index}>
              <button
                type="button"
                onClick={() => setOpenIndex(openIndex === index ? null : index)}
                className="w-full text-left px-space-lg py-space-sm grid grid-cols-[1fr_repeat(5,80px)_24px] gap-space-sm items-center hover:bg-surface-container-low cursor-pointer font-body-sm text-body-sm"
              >
                <span className="truncate">
                  {row.refused && <span className="text-on-tertiary-container font-semibold">[từ chối] </span>}
                  {!row.hit_expected_source && <span className="text-error font-semibold">[miss nguồn] </span>}
                  {row.question}
                </span>
                {METRICS.map((m) => (
                  <span key={m.key} className="font-mono text-right" title={m.label}>
                    {fmtScore(row[m.key] as number | null, 2)}
                  </span>
                ))}
                <span className="font-mono text-right font-bold text-primary">{fmtScore(avg, 2)}</span>
                <span className="material-symbols-outlined text-[18px]">{openIndex === index ? 'expand_less' : 'expand_more'}</span>
              </button>
              {openIndex === index && (
                <div className="px-space-lg pb-space-md grid grid-cols-1 lg:grid-cols-2 gap-space-md bg-surface-container-low/40">
                  <div>
                    <div className="font-label-sm text-label-sm uppercase font-mono text-on-surface-variant mb-1">Câu trả lời</div>
                    <AnswerText text={row.answer} />
                  </div>
                  <div className="flex flex-col gap-space-sm">
                    <div>
                      <div className="font-label-sm text-label-sm uppercase font-mono text-on-surface-variant mb-1">Đáp án kỳ vọng</div>
                      <p className="font-body-sm text-body-sm">{row.expected_answer}</p>
                    </div>
                    <div className="font-label-sm text-label-sm font-mono text-on-surface-variant">
                      Nguồn kỳ vọng: {row.expected_source || '—'} · {row.retrieval_method} · {fmtMs(row.latency_ms)}
                    </div>
                    <div className="font-label-sm text-label-sm font-mono text-on-surface-variant break-all">
                      {row.source_ids.join(' · ')}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
        <div className="px-space-lg py-space-xs bg-surface-container-low font-label-sm text-label-sm font-mono text-on-surface-variant">
          Cột: faithfulness · relevancy · recall · precision · trung bình
        </div>
      </Card>
    </div>
  );
};
