import React, { useEffect, useState } from 'react';
import { api, ChunkRecord, DocumentInfo, fmtBytes, useApi } from '../api';
import { Card, CardTitle, Empty, ErrorBox, Kpi, Loading, TypeBadge } from '../components/ui';

export const DatasetView: React.FC = () => {
  const docs = useApi('documents', api.documents);
  const config = useApi('config', api.config);
  const [filter, setFilter] = useState<'all' | 'legal' | 'news'>('all');
  const [selected, setSelected] = useState<DocumentInfo | null>(null);
  const [chunks, setChunks] = useState<ChunkRecord[] | null>(null);
  const [chunkError, setChunkError] = useState<string | null>(null);
  const [chunkQuery, setChunkQuery] = useState('');

  const documents = docs.data?.documents ?? [];

  useEffect(() => {
    if (!selected && documents.length) setSelected(documents[0]);
  }, [documents, selected]);

  useEffect(() => {
    if (!selected) return;
    setChunks(null);
    setChunkError(null);
    api
      .chunks(selected.id)
      .then((data) => setChunks(data.chunks))
      .catch((error: Error) => setChunkError(error.message));
  }, [selected]);

  if (docs.loading) return <Loading />;
  if (docs.error) return <ErrorBox error={docs.error} onRetry={docs.reload} />;

  const legal = documents.filter((d) => d.doc_type === 'legal');
  const news = documents.filter((d) => d.doc_type === 'news');
  const filtered = documents.filter((d) => filter === 'all' || d.doc_type === filter);
  const cfg = config.data;
  const visibleChunks = (chunks ?? []).filter(
    (chunk) => !chunkQuery.trim() || chunk.content.toLowerCase().includes(chunkQuery.trim().toLowerCase()),
  );

  return (
    <div className="flex flex-col w-full gap-space-lg pb-space-xl">
      <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-5 gap-space-md">
        <Kpi label="Tài liệu legal" icon="gavel" value={legal.length} hint={`${legal.reduce((s, d) => s + d.chunks, 0)} chunks`} />
        <Kpi label="Bài news" icon="newspaper" value={news.length} hint={`${news.reduce((s, d) => s + d.chunks, 0)} chunks`} />
        <Kpi
          label="Tổng chunks"
          icon="data_object"
          value={docs.data!.total_chunks.toLocaleString('vi-VN')}
          hint={`TB ${docs.data!.avg_chunk_chars} ký tự / chunk`}
        />
        <Kpi
          label="Vector dimension"
          icon="scatter_plot"
          value={cfg ? cfg.embedding_dim.toLocaleString('vi-VN') : '—'}
          hint={cfg ? `${cfg.embedding_provider} / ${cfg.embedding_model}` : undefined}
        />
        <Kpi
          label="ChromaDB"
          icon="database"
          value={cfg?.collection_name ?? '—'}
          hint={cfg ? `${cfg.collection_count} vectors · ${cfg.distance}` : undefined}
        />
      </div>

      {docs.data!.orphan_chunks > 0 && (
        <div className="bg-tertiary-fixed/50 rounded-xl p-space-md font-body-sm text-body-sm text-on-tertiary-fixed-variant">
          ChromaDB còn {docs.data!.orphan_chunks} chunk không thuộc file nào trong <code>data/standardized</code>. Chạy lại{' '}
          <code className="font-mono">python -m src.task4_chunking_indexing</code> để đồng bộ.
        </div>
      )}

      <Card className="p-space-lg flex flex-col gap-space-md">
        <CardTitle
          icon="sync_alt"
          title="Quy trình nạp dữ liệu"
          subtitle="data/landing → data/standardized → chunks → embeddings → ChromaDB"
        />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-space-sm">
          {[
            ['01. LANDING', 'Thu thập', `${documents.filter((d) => d.landing_file).length} file gốc (PDF/JSON)`, 'task1 · task2'],
            ['02. STANDARDIZE', 'Markdown', `${documents.length} file .md`, 'task3_convert_markdown'],
            [
              '03. CHUNKING',
              'Phân đoạn',
              cfg ? `${cfg.chunking_method} (${cfg.chunk_size}, overlap ${cfg.chunk_overlap})` : '—',
              `${docs.data!.total_chunks} chunks`,
            ],
            ['04. INDEX', 'Embedding + Chroma', cfg ? cfg.embedding_model : '—', cfg ? `${cfg.distance} space` : ''],
          ].map(([step, name, detail, foot]) => (
            <div key={step} className="bg-surface-container-low p-space-sm rounded-lg border border-slate-200/40">
              <div className="flex items-center justify-between font-mono font-label-sm text-label-sm text-on-surface-variant">
                {step}
                <span className="material-symbols-outlined text-secondary text-[18px]">check_circle</span>
              </div>
              <div className="font-headline-sm text-headline-sm text-primary font-semibold mt-space-xs">{name}</div>
              <div className="font-body-sm text-body-sm text-on-surface-variant truncate" title={detail}>
                {detail}
              </div>
              <div className="font-label-sm text-label-sm text-on-surface-variant font-mono mt-space-xs">{foot}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card className="overflow-hidden">
        <div className="p-space-lg flex flex-col md:flex-row md:items-center justify-between gap-space-md border-b border-slate-100">
          <div className="flex items-center gap-space-sm">
            <span className="font-headline-sm text-headline-sm text-primary font-bold">Danh sách tài liệu</span>
            <span className="bg-surface-container px-space-sm py-0.5 rounded-full font-label-sm text-label-sm text-primary font-bold font-mono">
              {documents.length} tệp
            </span>
            <button type="button" onClick={docs.reload} className="p-1 rounded hover:bg-surface-container cursor-pointer" title="Tải lại">
              <span className="material-symbols-outlined text-[18px]">refresh</span>
            </button>
          </div>
          <div className="flex items-center gap-space-xs bg-surface-container-low p-1 rounded-lg">
            {(['all', 'legal', 'news'] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setFilter(tab)}
                className={`px-space-md py-1.5 rounded-lg text-body-sm font-body-sm cursor-pointer ${
                  filter === tab ? 'bg-surface-container-lowest text-primary shadow-sm font-semibold' : 'text-on-surface-variant'
                }`}
              >
                {tab === 'all' ? `Tất cả (${documents.length})` : tab === 'legal' ? `legal (${legal.length})` : `news (${news.length})`}
              </button>
            ))}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left font-body-md text-body-md">
            <thead>
              <tr className="bg-surface-container-low text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider font-mono">
                <th className="py-space-sm px-space-lg">Tài liệu</th>
                <th className="py-space-sm px-space-md">Loại</th>
                <th className="py-space-sm px-space-md">File gốc / URL</th>
                <th className="py-space-sm px-space-md">Markdown</th>
                <th className="py-space-sm px-space-md">Chunks</th>
                <th className="py-space-sm px-space-lg text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((doc) => (
                <tr
                  key={doc.id}
                  onClick={() => setSelected(doc)}
                  className={`cursor-pointer ${selected?.id === doc.id ? 'bg-surface-container/50' : 'hover:bg-surface-container-low'}`}
                >
                  <td className="py-space-md px-space-lg">
                    <div className="flex items-center gap-space-sm">
                      <span className="w-10 h-8 rounded flex items-center justify-center font-mono font-bold text-label-sm bg-surface-container text-secondary">
                        {doc.landing_format ?? 'MD'}
                      </span>
                      <div className="min-w-0">
                        <div className="font-semibold text-primary max-w-[360px] truncate" title={doc.title}>
                          {doc.title}
                        </div>
                        <div className="font-label-sm text-label-sm font-mono text-on-surface-variant">{doc.id}</div>
                      </div>
                    </div>
                  </td>
                  <td className="py-space-md px-space-md">
                    <TypeBadge type={doc.doc_type} />
                  </td>
                  <td className="py-space-md px-space-md font-label-sm text-label-sm font-mono">
                    {doc.url ? (
                      <a
                        href={doc.url}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="text-secondary hover:underline truncate max-w-[240px] block"
                        title={doc.url}
                      >
                        {doc.url}
                      </a>
                    ) : (
                      <span className="truncate max-w-[240px] block" title={doc.landing_file ?? ''}>
                        {doc.landing_file ?? '—'}
                      </span>
                    )}
                    <span className="text-on-surface-variant">{fmtBytes(doc.landing_bytes)}</span>
                  </td>
                  <td className="py-space-md px-space-md font-label-sm text-label-sm font-mono text-on-surface-variant">
                    {doc.markdown_chars.toLocaleString('vi-VN')} ký tự
                    <br />
                    {fmtBytes(doc.markdown_bytes)}
                  </td>
                  <td className="py-space-md px-space-md">
                    <span
                      className={`font-label-sm text-label-sm font-mono font-bold px-space-xs py-0.5 rounded ${
                        doc.chunks ? 'bg-surface-container text-primary' : 'bg-error-container text-error'
                      }`}
                    >
                      {doc.chunks ? `${doc.chunks} chunks` : 'chưa index'}
                    </span>
                  </td>
                  <td className="py-space-md px-space-lg text-right">
                    <a
                      href={api.markdownUrl(doc.id)}
                      target="_blank"
                      rel="noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="inline-flex p-1 rounded hover:bg-surface-container text-on-surface-variant hover:text-primary"
                      title="Mở markdown đã chuẩn hoá"
                    >
                      <span className="material-symbols-outlined text-[20px]">description</span>
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {selected && (
        <Card className="overflow-hidden">
          <div className="p-space-lg bg-surface-container-low border-b border-slate-200 flex flex-col gap-space-sm">
            <CardTitle
              icon="splitscreen"
              title={selected.title}
              subtitle={`${selected.id} · ${selected.chunks} chunks · ${selected.markdown_chars.toLocaleString('vi-VN')} ký tự`}
              right={
                <input
                  value={chunkQuery}
                  onChange={(e) => setChunkQuery(e.target.value)}
                  placeholder="Lọc chunk theo từ khoá…"
                  className="bg-surface-container-lowest rounded-lg px-space-md py-1.5 font-body-sm text-body-sm border border-slate-200/60 focus:outline-none w-64"
                />
              }
            />
          </div>
          <div className="p-space-lg max-h-[560px] overflow-y-auto grid grid-cols-1 lg:grid-cols-2 gap-space-sm">
            {chunkError && <ErrorBox error={chunkError} />}
            {!chunks && !chunkError && <Loading label="Đang tải chunks từ ChromaDB…" />}
            {chunks && visibleChunks.length === 0 && <Empty icon="search_off">Không có chunk nào khớp.</Empty>}
            {visibleChunks.map((chunk) => (
              <div key={chunk.id} className="bg-surface-container-low rounded-lg p-space-md border border-slate-200/40">
                <div className="flex items-center justify-between font-mono font-label-sm text-label-sm mb-space-xs">
                  <span className="font-bold text-secondary">CHUNK #{chunk.metadata.chunk_index}</span>
                  <span className="text-on-surface-variant">{chunk.chars} ký tự</span>
                </div>
                <p className="font-body-sm text-body-sm text-on-surface whitespace-pre-line line-clamp-[10]">{chunk.content}</p>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};
