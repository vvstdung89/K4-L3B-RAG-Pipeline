import React from 'react';
import { PageTab } from '../types';
import { ChatResult, fmtMs, fmtScore, RankedChunk } from '../api';
import { AnswerText, Card, CardTitle, Empty, MethodBadge, TypeBadge } from '../components/ui';

interface PipelineViewProps {
  result: ChatResult | null;
  onNavigate: (tab: PageTab) => void;
}

type StageStatus = 'success' | 'skip' | 'fallback' | 'fail';

const STATUS_STYLE: Record<StageStatus, string> = {
  success: 'border-secondary/40 bg-secondary/5',
  skip: 'border-slate-200 bg-surface-container-low opacity-70',
  fallback: 'border-tertiary-fixed-dim bg-tertiary-fixed/30',
  fail: 'border-error/40 bg-error-container/30',
};

const ChunkList: React.FC<{ title: string; items: RankedChunk[]; scoreLabel: string }> = ({ title, items, scoreLabel }) => (
  <div className="flex flex-col gap-space-xs min-w-0">
    <div className="font-label-sm text-label-sm uppercase tracking-wider font-semibold text-on-surface-variant font-mono">
      {title} ({items.length})
    </div>
    {items.length === 0 && <div className="font-body-sm text-body-sm text-on-surface-variant italic">Không chạy / không có kết quả</div>}
    {items.map((item) => (
      <div key={item.id} className="bg-surface-container-low rounded-lg p-space-sm border border-slate-200/40" title={item.content}>
        <div className="flex items-center justify-between gap-space-xs font-mono font-label-sm text-label-sm">
          <span className="font-bold text-primary">#{item.rank}</span>
          <span className="text-secondary">
            {scoreLabel} {fmtScore(item.score, 4)}
          </span>
        </div>
        <div className="font-body-sm text-body-sm text-on-surface truncate">{item.title}</div>
        <div className="font-label-sm text-label-sm text-on-surface-variant font-mono truncate">
          {item.source} · #{item.chunk_index}
        </div>
      </div>
    ))}
  </div>
);

export const PipelineView: React.FC<PipelineViewProps> = ({ result, onNavigate }) => {
  if (!result) {
    return (
      <Card className="p-space-xl">
        <Empty icon="account_tree">
          Chưa có lượt truy vấn nào để trace.
          <button
            type="button"
            onClick={() => onNavigate('tro-chuyen')}
            className="mt-space-sm px-space-md py-space-xs rounded-lg bg-primary text-on-primary cursor-pointer"
          >
            Đặt câu hỏi ở tab Trò chuyện
          </button>
        </Empty>
      </Card>
    );
  }

  const t = result.timings;
  const belowThreshold = result.fallback.triggered;
  const stages: { num: string; name: string; status: StageStatus; detail: string; ms?: number }[] = [
    { num: '1', name: 'Input', status: 'success', detail: `${result.query.length} ký tự · top_k=${result.top_k}` },
    { num: '2', name: 'Dense (cosine)', status: 'success', detail: `${result.dense.length} ứng viên · top-1 ${fmtScore(result.best_dense_score)}`, ms: t.dense_ms },
    {
      num: '3',
      name: 'BM25',
      status: result.use_reranking ? 'success' : 'skip',
      detail: result.use_reranking ? `${result.bm25.length} ứng viên` : 'Tắt (config A dense-only)',
      ms: t.bm25_ms,
    },
    {
      num: '4',
      name: 'RRF fusion',
      status: result.use_reranking ? 'success' : 'skip',
      detail: result.use_reranking ? `k=60 → ${result.final.length} chunks` : 'Bỏ qua',
      ms: t.rrf_ms,
    },
    {
      num: '5',
      name: 'Ngưỡng fallback',
      status: belowThreshold ? 'fallback' : 'success',
      detail: `${fmtScore(result.best_dense_score)} ${belowThreshold ? '<' : '≥'} ${result.score_threshold}`,
    },
    {
      num: '6',
      name: 'PageIndex',
      status: !belowThreshold ? 'skip' : result.fallback.used ? 'success' : 'fail',
      detail: !belowThreshold
        ? 'Không cần'
        : result.fallback.used
          ? 'Dùng kết quả PageIndex'
          : result.fallback.error ?? 'Không có kết quả → giữ hybrid',
      ms: t.pageindex_ms,
    },
    {
      num: '7',
      name: 'LLM generation',
      status: result.error ? 'fail' : 'success',
      detail: result.generator,
      ms: t.llm_ms,
    },
    {
      num: '8',
      name: 'Citation check',
      status: result.refused ? 'fallback' : 'success',
      detail: result.refused ? 'Từ chối an toàn' : `Trích dẫn [${result.cited.join('][')}]`,
    },
  ];

  const waterfall = [
    ['Dense', t.dense_ms],
    ['BM25', t.bm25_ms],
    ['RRF', t.rrf_ms],
    ['PageIndex', t.pageindex_ms],
    ['LLM', t.llm_ms],
  ].filter(([, ms]) => ms !== undefined) as [string, number][];
  const total = t.total_ms || waterfall.reduce((sum, [, ms]) => sum + ms, 0) || 1;
  let offset = 0;

  return (
    <div className="flex flex-col gap-space-lg pb-space-xl">
      <Card className="p-space-lg flex flex-col gap-space-xs">
        <div className="flex flex-wrap items-center gap-space-sm">
          <MethodBadge method={result.retrieval_source} />
          <span className="font-label-sm text-label-sm text-on-surface-variant font-mono">
            {new Date(result.timestamp).toLocaleString('vi-VN')} · tổng {fmtMs(t.total_ms)}
          </span>
        </div>
        <h1 className="font-headline-lg text-headline-lg text-primary">“{result.query}”</h1>
      </Card>

      <Card className="p-space-lg flex flex-col gap-space-md">
        <CardTitle icon="account_tree" title="Các bước pipeline" subtitle="Trace của lượt hỏi gần nhất (src/api_server.py · trace_retrieval)" />
        <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-space-sm">
          {stages.map((stage) => (
            <div key={stage.num} className={`rounded-lg p-space-sm border ${STATUS_STYLE[stage.status]}`}>
              <div className="flex items-center justify-between font-mono font-label-sm text-label-sm text-on-surface-variant">
                <span>{stage.num.padStart(2, '0')}</span>
                <span>{stage.ms !== undefined ? fmtMs(stage.ms) : stage.status}</span>
              </div>
              <div className="font-body-sm text-body-sm font-semibold text-primary mt-1">{stage.name}</div>
              <div className="font-label-sm text-label-sm text-on-surface-variant break-words">{stage.detail}</div>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-space-lg">
        <Card className="xl:col-span-7 p-space-lg flex flex-col gap-space-md">
          <CardTitle icon="manage_search" title="Kết quả từng retriever" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-space-md">
            <ChunkList title="Dense" items={result.dense} scoreLabel="cos" />
            <ChunkList title="BM25" items={result.bm25} scoreLabel="bm25" />
            <ChunkList title={result.fallback.used ? 'PageIndex (final)' : 'Final (RRF)'} items={result.final} scoreLabel="score" />
          </div>
        </Card>

        <div className="xl:col-span-5 flex flex-col gap-space-lg">
          <Card className="p-space-lg flex flex-col gap-space-sm">
            <CardTitle icon="timeline" title="Thời gian xử lý" subtitle={`Tổng ${fmtMs(t.total_ms)}`} />
            {waterfall.map(([name, ms]) => {
              const left = (offset / total) * 100;
              offset += ms;
              return (
                <div key={name} className="grid grid-cols-[80px_1fr_70px] items-center gap-space-sm font-label-sm text-label-sm font-mono">
                  <span className="text-on-surface-variant">{name}</span>
                  <div className="relative h-3 bg-surface-container rounded">
                    <div
                      className="absolute inset-y-0 bg-secondary rounded"
                      style={{ left: `${left}%`, width: `${Math.max(0.5, (ms / total) * 100)}%` }}
                    ></div>
                  </div>
                  <span className="text-right text-primary">{fmtMs(ms)}</span>
                </div>
              );
            })}
          </Card>

          <Card className="p-space-lg flex flex-col gap-space-sm">
            <CardTitle icon="chat" title="Câu trả lời" subtitle={result.generator} />
            <AnswerText text={result.answer} maxCite={result.sources.length} />
            {result.sources.length > 0 && (
              <div className="flex flex-col gap-1 pt-space-xs border-t border-slate-100">
                {result.sources.map((source) => (
                  <div key={source.id} className="flex items-center gap-space-xs font-label-sm text-label-sm">
                    <span className={`font-bold ${source.cited ? 'text-amber-800' : 'text-on-surface-variant'}`}>[{source.rank}]</span>
                    <TypeBadge type={source.doc_type} />
                    <span className="truncate">{source.title}</span>
                    <span className="font-mono text-on-surface-variant">#{source.chunk_index}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
};
