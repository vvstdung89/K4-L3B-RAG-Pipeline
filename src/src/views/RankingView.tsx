import React, { useEffect, useState } from 'react';
import { api, fmtMs, fmtScore, RankedChunk, RetrievalTrace } from '../api';
import { Card, CardTitle, Empty, ErrorBox, Loading, MethodBadge, ScoreBar, TypeBadge } from '../components/ui';

interface RankingViewProps {
  initialQuery?: string;
}

const Column: React.FC<{
  title: string;
  subtitle: string;
  items: RankedChunk[];
  max: number;
  threshold?: number;
  selectedId: string | null;
  onSelect: (item: RankedChunk) => void;
}> = ({ title, subtitle, items, max, threshold, selectedId, onSelect }) => (
  <Card className="p-space-md flex flex-col gap-space-sm min-w-0">
    <div>
      <div className="font-headline-sm text-headline-sm text-primary font-bold">{title}</div>
      <div className="font-label-sm text-label-sm text-on-surface-variant">{subtitle}</div>
    </div>
    {items.length === 0 && <div className="font-body-sm text-body-sm italic text-on-surface-variant">Không có kết quả.</div>}
    {items.map((item) => (
      <button
        key={item.id}
        type="button"
        onClick={() => onSelect(item)}
        className={`text-left rounded-lg p-space-sm border cursor-pointer ${
          selectedId === item.id ? 'border-secondary bg-secondary/5' : 'border-slate-200/50 bg-surface-container-low hover:bg-surface-container'
        }`}
      >
        <div className="flex items-center justify-between font-mono font-label-sm text-label-sm">
          <span className="font-bold text-primary">#{item.rank}</span>
          <span className="text-secondary">{fmtScore(item.score, 4)}</span>
        </div>
        <ScoreBar value={item.score} max={max} threshold={threshold} />
        <div className="font-body-sm text-body-sm text-on-surface truncate mt-1">{item.title}</div>
        <div className="font-label-sm text-label-sm text-on-surface-variant font-mono truncate">
          {item.source} · #{item.chunk_index}
        </div>
      </button>
    ))}
  </Card>
);

export const RankingView: React.FC<RankingViewProps> = ({ initialQuery }) => {
  const [query, setQuery] = useState(initialQuery || 'Điều kiện cấp thẻ hướng dẫn viên du lịch quốc tế là gì?');
  const [topK, setTopK] = useState(5);
  const [trace, setTrace] = useState<RetrievalTrace | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<RankedChunk | null>(null);

  const run = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.retrieve(query.trim(), topK, true);
      setTrace(data);
      setSelected(data.final[0] ?? null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    run();
    // chỉ chạy lần đầu với câu hỏi gần nhất
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const maxOf = (items: RankedChunk[]) => Math.max(1e-9, ...items.map((i) => i.score));

  return (
    <div className="flex flex-col gap-space-lg pb-space-xl">
      <Card className="p-space-lg flex flex-col gap-space-md">
        <CardTitle icon="leaderboard" title="So sánh xếp hạng Dense · BM25 · Hybrid RRF" subtitle="Chỉ chạy retrieval, không gọi LLM" />
        <form
          className="flex flex-col md:flex-row gap-space-sm"
          onSubmit={(e) => {
            e.preventDefault();
            run();
          }}
        >
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 bg-surface-container-low rounded-lg px-space-md py-2 font-body-md text-body-md border border-slate-200/50 focus:outline-none"
          />
          <div className="flex items-center gap-space-xs font-label-sm text-label-sm text-on-surface-variant">
            top_k
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className="bg-surface-container-low rounded px-2 py-2 font-mono border border-slate-200/50"
            >
              {[3, 5, 8, 10].map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </div>
          <button type="submit" disabled={loading} className="px-space-lg py-2 rounded-lg bg-primary text-on-primary cursor-pointer disabled:opacity-50">
            {loading ? 'Đang chạy…' : 'Chạy retrieval'}
          </button>
        </form>
        {trace && (
          <div className="flex flex-wrap gap-space-md font-label-sm text-label-sm font-mono text-on-surface-variant">
            <span>
              cos top-1 <strong className="text-primary">{fmtScore(trace.best_dense_score)}</strong> / ngưỡng {trace.score_threshold}
            </span>
            <span>dense {fmtMs(trace.timings.dense_ms)}</span>
            <span>bm25 {fmtMs(trace.timings.bm25_ms)}</span>
            <span>
              nguồn cuối: <MethodBadge method={trace.retrieval_source} />
            </span>
            {trace.fallback.triggered && !trace.fallback.used && (
              <span className="text-on-tertiary-container">dưới ngưỡng → PageIndex không khả dụng, giữ hybrid</span>
            )}
          </div>
        )}
      </Card>

      {error && <ErrorBox error={error} onRetry={run} />}
      {loading && !trace && <Loading label="Đang truy xuất…" />}

      {trace && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-space-md">
            <Column
              title="Dense (cosine)"
              subtitle={`${trace.dense.length} ứng viên · vạch đỏ = ngưỡng`}
              items={trace.dense}
              max={1}
              threshold={trace.score_threshold}
              selectedId={selected?.id ?? null}
              onSelect={setSelected}
            />
            <Column
              title="BM25 (từ khoá)"
              subtitle={`${trace.bm25.length} ứng viên`}
              items={trace.bm25}
              max={maxOf(trace.bm25)}
              selectedId={selected?.id ?? null}
              onSelect={setSelected}
            />
            <Column
              title={trace.fallback.used ? 'PageIndex (final)' : 'Hybrid RRF (final)'}
              subtitle="RRF(d) = Σ 1/(60 + rank)"
              items={trace.final}
              max={maxOf(trace.final)}
              selectedId={selected?.id ?? null}
              onSelect={setSelected}
            />
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-12 gap-space-lg">
            <Card className="xl:col-span-7 overflow-hidden">
              <div className="p-space-md border-b border-slate-100">
                <CardTitle icon="swap_vert" title="Thay đổi thứ hạng sau RRF" />
              </div>
              <table className="w-full text-left font-body-sm text-body-sm">
                <thead>
                  <tr className="bg-surface-container-low font-label-sm text-label-sm uppercase font-mono text-on-surface-variant">
                    <th className="px-space-md py-space-xs">Final</th>
                    <th className="px-space-md py-space-xs">Chunk</th>
                    <th className="px-space-md py-space-xs">Dense</th>
                    <th className="px-space-md py-space-xs">BM25</th>
                    <th className="px-space-md py-space-xs">Cosine</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {trace.final.map((item) => (
                    <tr key={item.id} onClick={() => setSelected(item)} className="cursor-pointer hover:bg-surface-container-low">
                      <td className="px-space-md py-space-xs font-mono font-bold text-primary">#{item.rank}</td>
                      <td className="px-space-md py-space-xs">
                        <div className="truncate max-w-[320px]">{item.title}</div>
                        <div className="font-mono font-label-sm text-label-sm text-on-surface-variant">#{item.chunk_index}</div>
                      </td>
                      <td className="px-space-md py-space-xs font-mono">{item.dense_rank ? `#${item.dense_rank}` : '—'}</td>
                      <td className="px-space-md py-space-xs font-mono">{item.bm25_rank ? `#${item.bm25_rank}` : '—'}</td>
                      <td className="px-space-md py-space-xs font-mono">{fmtScore(item.dense_score)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>

            <Card className="xl:col-span-5 p-space-lg flex flex-col gap-space-sm">
              {!selected ? (
                <Empty>Chọn một chunk để xem nội dung.</Empty>
              ) : (
                <>
                  <div className="flex items-center gap-space-xs flex-wrap">
                    <MethodBadge method={selected.retrieval_method} />
                    <TypeBadge type={selected.doc_type} />
                    <span className="font-mono font-label-sm text-label-sm text-on-surface-variant">{selected.id}</span>
                  </div>
                  <div className="font-headline-sm text-headline-sm text-primary font-bold">{selected.title}</div>
                  <p className="font-body-sm text-body-sm whitespace-pre-line max-h-[360px] overflow-y-auto">{selected.content}</p>
                  {selected.url && (
                    <a href={selected.url} target="_blank" rel="noreferrer" className="font-label-sm text-label-sm text-secondary hover:underline break-all">
                      {selected.url}
                    </a>
                  )}
                </>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
};
