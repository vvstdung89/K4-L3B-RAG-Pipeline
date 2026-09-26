import React from 'react';
import { api, useApi } from '../api';
import { Card, CardTitle, ErrorBox, Loading } from '../components/ui';

const Row: React.FC<{ label: string; value: React.ReactNode; source?: string }> = ({ label, value, source }) => (
  <div className="flex items-center justify-between gap-space-sm bg-surface-container-low p-space-sm rounded-lg border border-slate-200/40">
    <div>
      <div className="font-body-sm text-body-sm text-on-surface">{label}</div>
      {source && <div className="font-label-sm text-label-sm font-mono text-on-surface-variant">{source}</div>}
    </div>
    <div className="font-mono font-body-sm text-body-sm font-semibold text-primary text-right break-all">{value}</div>
  </div>
);

const Flag: React.FC<{ on: boolean; onText?: string; offText?: string }> = ({ on, onText = 'có', offText = 'chưa cấu hình' }) => (
  <span className={`px-2 py-0.5 rounded-full font-label-sm text-label-sm ${on ? 'bg-secondary/10 text-secondary' : 'bg-surface-container text-on-surface-variant'}`}>
    {on ? onText : offText}
  </span>
);

export const SettingsView: React.FC = () => {
  const config = useApi('config', api.config);
  if (config.loading) return <Loading />;
  if (config.error) return <ErrorBox error={config.error} onRetry={config.reload} />;
  const c = config.data!;

  return (
    <div className="flex flex-col gap-space-lg pb-space-xl">
      <Card className="p-space-lg">
        <CardTitle
          icon="tune"
          title="Cấu hình đang chạy"
          subtitle={
            <>
              Đọc từ backend (<code className="font-mono">.env</code> và hằng số trong <code className="font-mono">src/task*.py</code>). Sửa{' '}
              <code className="font-mono">.env</code> rồi khởi động lại <code className="font-mono">python -m src.api_server</code> để áp dụng.
            </>
          }
          right={
            <button type="button" onClick={config.reload} className="px-space-md py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high cursor-pointer font-body-sm text-body-sm">
              Tải lại
            </button>
          }
        />
      </Card>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-space-lg">
        <Card className="p-space-lg flex flex-col gap-space-sm">
          <CardTitle icon="smart_toy" title="LLM & Embedding" />
          <Row label="LLM provider" value={c.llm_provider} source="LLM_PROVIDER" />
          <Row label="LLM model" value={c.llm_model} source="LLM_MODEL" />
          <Row label="Temperature / top_p" value={`${c.temperature} / ${c.top_p}`} source="task10_generation.py" />
          <Row label="Embedding" value={`${c.embedding_provider} / ${c.embedding_model}`} source="EMBEDDING_PROVIDER · EMBEDDING_MODEL" />
          <Row label="Vector dimension" value={c.embedding_dim || 'không rõ'} />
          <div className="flex flex-wrap gap-space-xs pt-space-xs">
            {Object.entries(c.api_keys).map(([name, set]) => (
              <span key={name} className="flex items-center gap-1 font-label-sm text-label-sm font-mono">
                {name} <Flag on={set} onText="đã đặt" />
              </span>
            ))}
          </div>
        </Card>

        <Card className="p-space-lg flex flex-col gap-space-sm">
          <CardTitle icon="manage_search" title="Retrieval" />
          <Row label="top_k mặc định" value={c.top_k} source="task10_generation.TOP_K" />
          <Row label="Ứng viên mỗi retriever" value={`top_k × ${c.candidate_multiplier}`} source="task9.CANDIDATE_MULTIPLIER" />
          <Row label="RRF k" value={c.rrf_k} source="task7_reranking" />
          <Row label="Ngưỡng fallback (cosine dense top-1)" value={c.score_threshold} source="SCORE_THRESHOLD" />
          <Row label="PageIndex fallback" value={<Flag on={c.pageindex_configured} onText="bật" />} source="PAGEINDEX_API_KEY" />
        </Card>

        <Card className="p-space-lg flex flex-col gap-space-sm">
          <CardTitle icon="database" title="Chunking & Vector store" />
          <Row label="Chunking" value={c.chunking_method} source="task4.CHUNKING_METHOD" />
          <Row label="Chunk size / overlap (ký tự)" value={`${c.chunk_size} / ${c.chunk_overlap}`} />
          <Row label="Collection" value={c.collection_name} source="chroma_db/" />
          <Row label="Số vector" value={c.collection_count.toLocaleString('vi-VN')} />
          <Row label="Khoảng cách" value={c.distance} />
        </Card>

        <Card className="p-space-lg flex flex-col gap-space-sm">
          <CardTitle icon="shield" title="Prompt & từ chối an toàn" />
          <Row label="Câu từ chối" value={c.refusal_message} />
          <pre className="bg-surface-container-low rounded-lg p-space-sm font-mono text-[12px] whitespace-pre-wrap text-on-surface border border-slate-200/40 max-h-72 overflow-y-auto">
            {c.system_prompt}
          </pre>
        </Card>
      </div>
    </div>
  );
};
