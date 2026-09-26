import React, { useRef, useState } from 'react';
import { PageTab } from '../types';
import { api, ChatResult, fmtMs, fmtScore } from '../api';
import { AnswerText, Card, MethodBadge, ScoreBar, TypeBadge } from '../components/ui';

export interface ChatTurn {
  id: string;
  query: string;
  askedAt: string;
  topK: number;
  useReranking: boolean;
  result?: ChatResult;
  error?: string;
}

interface ChatViewProps {
  turns: ChatTurn[];
  setTurns: React.Dispatch<React.SetStateAction<ChatTurn[]>>;
  onNavigate: (tab: PageTab) => void;
}

const SUGGESTIONS = [
  'Khách du lịch có những quyền gì theo Luật Du lịch?',
  'Điều kiện cấp thẻ hướng dẫn viên du lịch quốc tế là gì?',
  'Công dân Nhật Bản được miễn visa vào Việt Nam bao nhiêu ngày?',
  'Gợi ý bãi biển đẹp nhất Việt Nam?',
];

const timeOf = (iso: string) => new Date(iso).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });

export const ChatView: React.FC<ChatViewProps> = ({ turns, setTurns, onNavigate }) => {
  const [input, setInput] = useState('');
  const [topK, setTopK] = useState(5);
  const [useReranking, setUseReranking] = useState(true);
  const [selectedTurnId, setSelectedTurnId] = useState<string | null>(null);
  const [activeCite, setActiveCite] = useState<number | null>(null);
  const [typeFilter, setTypeFilter] = useState<'all' | 'legal' | 'news'>('all');
  const cardRefs = useRef<Record<number, HTMLDivElement | null>>({});

  const pending = turns.some((turn) => !turn.result && !turn.error);
  const answered = turns.filter((turn) => turn.result);
  const selected =
    turns.find((turn) => turn.id === selectedTurnId && turn.result) ?? answered[answered.length - 1] ?? null;
  const result = selected?.result ?? null;

  const send = async (question: string) => {
    const query = question.trim();
    if (!query || pending) return;
    const turn: ChatTurn = {
      id: `${Date.now()}`,
      query,
      askedAt: new Date().toISOString(),
      topK,
      useReranking,
    };
    setTurns((prev) => [...prev, turn]);
    setInput('');
    try {
      const response = await api.chat(query, topK, useReranking);
      setTurns((prev) => prev.map((t) => (t.id === turn.id ? { ...t, result: response } : t)));
      setSelectedTurnId(turn.id);
      setActiveCite(response.cited[0] ?? null);
    } catch (error) {
      setTurns((prev) => prev.map((t) => (t.id === turn.id ? { ...t, error: (error as Error).message } : t)));
    }
  };

  const focusCite = (turnId: string, n: number) => {
    setSelectedTurnId(turnId);
    setActiveCite(n);
    setTypeFilter('all');
    requestAnimationFrame(() => cardRefs.current[n]?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }));
  };

  const sources = (result?.sources ?? []).filter((s) => typeFilter === 'all' || s.doc_type === typeFilter);

  return (
    <div className="grid grid-cols-1 xl:grid-cols-12 gap-space-lg w-full items-start">
      <div className="xl:col-span-7 flex flex-col gap-space-lg w-full">
        <Card className="p-space-lg flex flex-col gap-space-xs">
          <span className="font-label-sm text-label-sm text-secondary uppercase tracking-wider font-semibold">
            Luật Du lịch 2017 · Visa nhập cảnh · Cẩm nang điểm đến
          </span>
          <h1 className="font-headline-lg text-headline-lg text-primary tracking-tight">Hỏi đáp du lịch Việt Nam</h1>
          <p className="font-body-md text-body-md text-on-surface-variant">
            Mọi câu trả lời đều dẫn nguồn [n] khớp với danh sách nguồn bên phải. Không đủ bằng chứng thì chatbot từ chối.
          </p>
          <div className="flex flex-wrap gap-space-xs pt-space-sm">
            {SUGGESTIONS.map((q) => (
              <button
                key={q}
                type="button"
                disabled={pending}
                onClick={() => send(q)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-low hover:bg-surface-container text-on-surface text-left cursor-pointer border border-slate-200/40 disabled:opacity-50"
              >
                <span className="material-symbols-outlined text-[15px] text-secondary">arrow_forward</span>
                <span className="font-body-sm text-body-sm font-medium">{q}</span>
              </button>
            ))}
          </div>
        </Card>

        <div className="flex flex-col gap-space-lg">
          {turns.length === 0 && (
            <div className="text-center text-on-surface-variant font-body-sm text-body-sm py-space-xl">
              Chưa có câu hỏi nào. Chọn một gợi ý hoặc nhập câu hỏi bên dưới.
            </div>
          )}
          {turns.map((turn) => (
            <React.Fragment key={turn.id}>
              <div className="flex items-start justify-end gap-space-sm pl-8">
                <div className="flex flex-col items-end gap-1">
                  <div className="bg-primary text-on-primary rounded-xl rounded-tr-xs px-space-md py-space-sm shadow-sm max-w-lg">
                    <p className="font-body-md text-body-md leading-relaxed">{turn.query}</p>
                  </div>
                  <span className="font-label-sm text-label-sm text-on-surface-variant">
                    Bạn • {timeOf(turn.askedAt)} • top_k={turn.topK} • {turn.useReranking ? 'hybrid RRF' : 'dense'}
                  </span>
                </div>
              </div>

              <div className="flex items-start gap-space-sm pr-4">
                <div className="w-8 h-8 rounded-lg bg-primary-container text-secondary-container flex items-center justify-center flex-shrink-0 mt-1">
                  <span className="material-symbols-outlined text-[18px]">travel_explore</span>
                </div>
                <div className="flex-1 min-w-0">
                  {!turn.result && !turn.error && (
                    <Card className="p-space-lg flex items-center gap-space-sm text-on-surface-variant">
                      <span className="material-symbols-outlined animate-spin text-[18px]">progress_activity</span>
                      Đang truy xuất và sinh câu trả lời…
                    </Card>
                  )}
                  {turn.error && (
                    <Card className="p-space-lg border-error/40 text-error font-body-sm text-body-sm">
                      Lỗi gọi backend: {turn.error}
                    </Card>
                  )}
                  {turn.result && (
                    <Card
                      className={`p-space-lg flex flex-col gap-space-md ${
                        selected?.id === turn.id ? 'ring-1 ring-secondary/40' : ''
                      } ${turn.result.refused ? 'border-tertiary-fixed-dim' : ''}`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-space-xs pb-space-xs border-b border-slate-100">
                        <div className="flex items-center gap-space-xs">
                          <MethodBadge method={turn.result.retrieval_source} />
                          <span className="font-label-sm text-label-sm text-on-surface-variant font-mono">
                            {turn.result.generator}
                          </span>
                        </div>
                        {turn.result.refused ? (
                          <span className="px-2.5 py-0.5 rounded-full bg-tertiary-fixed text-on-tertiary-fixed-variant font-label-sm text-label-sm font-semibold">
                            Từ chối an toàn
                          </span>
                        ) : (
                          <span className="px-2.5 py-0.5 rounded-full bg-surface-container font-label-sm text-label-sm text-on-surface-variant">
                            {turn.result.cited.length}/{turn.result.sources.length} nguồn được trích dẫn
                          </span>
                        )}
                      </div>

                      <AnswerText
                        text={turn.result.answer}
                        maxCite={turn.result.sources.length}
                        onCite={(n) => focusCite(turn.id, n)}
                      />

                      {turn.result.refused && (
                        <div className="bg-surface-container-low rounded-lg p-space-sm font-body-sm text-body-sm text-on-surface-variant">
                          Điểm cosine cao nhất (dense):{' '}
                          <strong className="font-mono">{fmtScore(turn.result.best_dense_score)}</strong> — ngưỡng fallback{' '}
                          <strong className="font-mono">{turn.result.score_threshold}</strong>.
                          {turn.result.fallback.triggered &&
                            !turn.result.fallback.used &&
                            ' PageIndex fallback không khả dụng nên dùng kết quả hybrid.'}
                          {turn.result.error && <div className="text-error mt-1">Provider lỗi: {turn.result.error}</div>}
                        </div>
                      )}

                      <div className="flex flex-wrap items-center justify-between gap-space-sm bg-surface-container-low/50 -mx-space-lg -mb-space-lg px-space-lg py-2.5 rounded-b-xl border-t border-slate-100">
                        <div className="flex items-center gap-space-md font-label-sm text-label-sm text-on-surface-variant">
                          <span className="flex items-center gap-1">
                            <span className="material-symbols-outlined text-[16px] text-secondary">dataset</span>
                            {turn.result.sources.length} nguồn
                          </span>
                          <span className="flex items-center gap-1">
                            <span className="material-symbols-outlined text-[16px]">timer</span>
                            <strong className="text-primary">{fmtMs(turn.result.timings.total_ms)}</strong>
                          </span>
                          <span className="flex items-center gap-1 font-mono">
                            cos top-1 {fmtScore(turn.result.best_dense_score)}
                          </span>
                        </div>
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => setSelectedTurnId(turn.id)}
                            className="px-2.5 py-1 rounded bg-surface-container hover:bg-surface-container-highest font-label-sm text-label-sm cursor-pointer"
                          >
                            Xem nguồn
                          </button>
                          <button
                            type="button"
                            onClick={() => onNavigate('pipeline-realtime')}
                            className="flex items-center gap-1 px-2.5 py-1 rounded bg-surface-container hover:bg-surface-container-highest font-label-sm text-label-sm cursor-pointer"
                          >
                            <span className="material-symbols-outlined text-[14px]">account_tree</span>
                            Pipeline
                          </button>
                          <button
                            type="button"
                            onClick={() => navigator.clipboard.writeText(turn.result!.answer)}
                            className="w-7 h-7 rounded hover:bg-surface-container text-on-surface-variant flex items-center justify-center cursor-pointer"
                            title="Sao chép câu trả lời"
                          >
                            <span className="material-symbols-outlined text-[16px]">content_copy</span>
                          </button>
                        </div>
                      </div>
                    </Card>
                  )}
                </div>
              </div>
            </React.Fragment>
          ))}
        </div>

        <Card className="p-space-md flex flex-col gap-space-sm sticky bottom-space-md">
          <div className="flex flex-wrap items-center justify-between gap-space-sm">
            <button
              type="button"
              onClick={() => setUseReranking(!useReranking)}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full font-label-sm text-label-sm cursor-pointer border ${
                useReranking
                  ? 'bg-secondary/10 text-secondary border-secondary/30'
                  : 'bg-surface-container-low text-on-surface-variant border-slate-200'
              }`}
            >
              <span className="material-symbols-outlined text-[15px]">{useReranking ? 'toggle_on' : 'toggle_off'}</span>
              Hybrid BM25 + RRF {useReranking ? '(bật)' : '(tắt — chỉ dense)'}
            </button>
            <div className="flex items-center gap-space-xs font-label-sm text-label-sm text-on-surface-variant">
              top_k
              <button type="button" onClick={() => setTopK(Math.max(3, topK - 1))} className="w-6 h-6 rounded bg-surface-container cursor-pointer">
                −
              </button>
              <span className="font-mono font-bold text-primary w-5 text-center">{topK}</span>
              <button type="button" onClick={() => setTopK(Math.min(10, topK + 1))} className="w-6 h-6 rounded bg-surface-container cursor-pointer">
                +
              </button>
              {turns.length > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    setTurns([]);
                    setSelectedTurnId(null);
                  }}
                  className="ml-space-sm px-2 py-1 rounded hover:bg-surface-container cursor-pointer"
                >
                  Xoá hội thoại
                </button>
              )}
            </div>
          </div>
          <form
            className="flex items-end gap-space-sm"
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
          >
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              rows={2}
              placeholder="Hỏi về Luật Du lịch, visa, điểm đến…"
              className="flex-1 resize-none bg-surface-container-low rounded-lg px-space-md py-space-sm font-body-md text-body-md focus:outline-none focus:bg-surface-container-lowest border border-slate-200/50"
            />
            <button
              type="submit"
              disabled={pending || !input.trim()}
              className="h-10 px-space-lg rounded-lg bg-primary text-on-primary flex items-center gap-1 cursor-pointer disabled:opacity-50"
            >
              <span className="material-symbols-outlined text-[18px]">send</span>
              Gửi
            </button>
          </form>
        </Card>
      </div>

      <div className="xl:col-span-5 flex flex-col gap-space-md xl:sticky xl:top-20">
        <Card className="p-space-md flex flex-col gap-space-sm">
          <div className="flex items-center justify-between">
            <span className="font-headline-sm text-headline-sm text-primary font-bold">Nguồn tham khảo</span>
            {result && <MethodBadge method={result.retrieval_source} />}
          </div>
          {selected && <div className="font-body-sm text-body-sm text-on-surface-variant truncate">“{selected.query}”</div>}
          <div className="flex gap-space-xs bg-surface-container-low p-1 rounded-lg">
            {(['all', 'legal', 'news'] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setTypeFilter(tab)}
                className={`flex-1 px-space-sm py-1 rounded font-body-sm text-body-sm cursor-pointer ${
                  typeFilter === tab ? 'bg-surface-container-lowest text-primary shadow-sm font-semibold' : 'text-on-surface-variant'
                }`}
              >
                {tab === 'all' ? 'Tất cả' : tab} ({(result?.sources ?? []).filter((s) => tab === 'all' || s.doc_type === tab).length})
              </button>
            ))}
          </div>
          {result && (
            <div className="font-label-sm text-label-sm text-on-surface-variant">
              Thanh điểm = cosine dense của chunk, vạch đỏ = ngưỡng {result.score_threshold}. Điểm hybrid là RRF (chỉ phản ánh thứ hạng).
            </div>
          )}
        </Card>

        <div className="flex flex-col gap-space-sm max-h-[calc(100vh-16rem)] overflow-y-auto pr-1">
          {!result && (
            <Card className="p-space-lg text-center text-on-surface-variant font-body-sm text-body-sm">
              Nguồn của câu trả lời sẽ hiển thị ở đây.
            </Card>
          )}
          {result && result.sources.length === 0 && (
            <Card className="p-space-lg text-center text-on-surface-variant font-body-sm text-body-sm">
              Không có nguồn đủ tin cậy cho câu hỏi này.
            </Card>
          )}
          {sources.map((source) => {
            const active = activeCite === source.rank;
            return (
              <div
                key={source.id}
                ref={(el) => {
                  cardRefs.current[source.rank] = el;
                }}
                onClick={() => setActiveCite(source.rank)}
                className={`bg-surface-container-lowest rounded-xl p-space-md border cursor-pointer transition-all ${
                  active ? 'border-amber-300 shadow-md' : 'border-slate-200/60'
                } ${source.cited ? '' : 'opacity-70'}`}
              >
                <div className="flex items-start justify-between gap-space-sm">
                  <div className="flex items-start gap-space-xs min-w-0">
                    <span
                      className={`px-1.5 rounded font-label-sm text-label-sm font-bold ${
                        source.cited ? 'bg-amber-100 text-amber-900 border border-amber-300' : 'bg-surface-container text-on-surface-variant'
                      }`}
                    >
                      [{source.rank}]
                    </span>
                    <div className="min-w-0">
                      <div className="font-body-sm text-body-sm font-semibold text-primary truncate" title={source.title}>
                        {source.title}
                      </div>
                      <div className="font-label-sm text-label-sm text-on-surface-variant font-mono truncate">
                        {source.source} · chunk #{source.chunk_index}
                      </div>
                    </div>
                  </div>
                  <TypeBadge type={source.doc_type} />
                </div>
                <div className="flex flex-wrap items-center gap-space-sm mt-space-xs font-label-sm text-label-sm text-on-surface-variant font-mono">
                  <MethodBadge method={source.retrieval_method} />
                  <span>score {fmtScore(source.score, 4)}</span>
                  <span>dense #{source.dense_rank ?? '—'}</span>
                  <span>bm25 #{source.bm25_rank ?? '—'}</span>
                  {!source.cited && <span className="italic">không được trích dẫn</span>}
                </div>
                {source.dense_score !== null && source.dense_score !== undefined && (
                  <div className="mt-space-xs flex items-center gap-space-xs">
                    <div className="flex-1">
                      <ScoreBar value={source.dense_score} threshold={result?.score_threshold} />
                    </div>
                    <span className="font-mono font-label-sm text-label-sm">{fmtScore(source.dense_score)}</span>
                  </div>
                )}
                <p
                  className={`mt-space-xs font-body-sm text-body-sm text-on-surface whitespace-pre-line ${
                    active ? '' : 'line-clamp-4'
                  }`}
                >
                  {source.content}
                </p>
                {source.url && (
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="mt-space-xs inline-flex items-center gap-1 font-label-sm text-label-sm text-secondary hover:underline break-all"
                  >
                    <span className="material-symbols-outlined text-[14px]">open_in_new</span>
                    {source.url}
                  </a>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
