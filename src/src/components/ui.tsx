import React from 'react';

export const Card: React.FC<{ className?: string; children: React.ReactNode }> = ({ className = '', children }) => (
  <div className={`bg-surface-container-lowest rounded-xl shadow-sm border border-slate-200/60 ${className}`}>{children}</div>
);

export const CardTitle: React.FC<{ icon: string; title: string; subtitle?: React.ReactNode; right?: React.ReactNode }> = ({
  icon,
  title,
  subtitle,
  right,
}) => (
  <div className="flex flex-wrap items-center justify-between gap-space-sm">
    <div className="flex items-center gap-space-sm min-w-0">
      <span className="w-8 h-8 rounded-lg bg-primary-container text-secondary-container flex items-center justify-center flex-shrink-0">
        <span className="material-symbols-outlined text-[18px]">{icon}</span>
      </span>
      <div className="min-w-0">
        <div className="font-headline-sm text-headline-sm text-primary font-bold">{title}</div>
        {subtitle && <div className="font-body-sm text-body-sm text-on-surface-variant">{subtitle}</div>}
      </div>
    </div>
    {right}
  </div>
);

export const Kpi: React.FC<{ label: string; value: React.ReactNode; hint?: React.ReactNode; icon: string }> = ({
  label,
  value,
  hint,
  icon,
}) => (
  <Card className="p-space-md flex flex-col justify-between gap-space-xs">
    <div className="flex items-center justify-between">
      <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider font-semibold font-mono">
        {label}
      </span>
      <span className="material-symbols-outlined text-[18px] text-secondary">{icon}</span>
    </div>
    <div className="font-headline-lg text-headline-lg text-primary font-bold font-mono truncate">{value}</div>
    {hint && <div className="font-label-sm text-label-sm text-on-surface-variant truncate">{hint}</div>}
  </Card>
);

export const Loading: React.FC<{ label?: string }> = ({ label = 'Đang tải dữ liệu…' }) => (
  <div className="flex items-center gap-space-sm text-on-surface-variant font-body-sm text-body-sm p-space-lg">
    <span className="material-symbols-outlined text-[18px] animate-spin">progress_activity</span>
    {label}
  </div>
);

export const ErrorBox: React.FC<{ error: string; onRetry?: () => void }> = ({ error, onRetry }) => (
  <div className="bg-error-container/40 border border-error/30 text-on-error-container rounded-xl p-space-md flex flex-wrap items-center gap-space-sm font-body-sm text-body-sm">
    <span className="material-symbols-outlined text-error text-[20px]">error</span>
    <span className="flex-1 min-w-0 break-words">
      Không lấy được dữ liệu từ backend: {error}. Kiểm tra <code className="font-mono">python -m src.api_server</code> đang chạy ở cổng 8000.
    </span>
    {onRetry && (
      <button type="button" onClick={onRetry} className="px-space-sm py-1 rounded bg-error text-on-error cursor-pointer">
        Thử lại
      </button>
    )}
  </div>
);

export const Empty: React.FC<{ icon?: string; children: React.ReactNode }> = ({ icon = 'info', children }) => (
  <div className="flex flex-col items-center justify-center text-center gap-space-xs p-space-xl text-on-surface-variant font-body-sm text-body-sm">
    <span className="material-symbols-outlined text-[32px] text-outline">{icon}</span>
    {children}
  </div>
);

const METHOD_STYLES: Record<string, string> = {
  hybrid: 'bg-secondary/10 text-secondary',
  dense: 'bg-primary-fixed text-on-primary-fixed-variant',
  bm25: 'bg-violet-100 text-violet-800',
  pageindex: 'bg-tertiary-fixed text-on-tertiary-fixed-variant',
  none: 'bg-surface-container text-on-surface-variant',
};

export const MethodBadge: React.FC<{ method: string }> = ({ method }) => (
  <span
    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-label-sm text-label-sm font-semibold font-mono ${
      METHOD_STYLES[method] || METHOD_STYLES.none
    }`}
  >
    <span className="w-1.5 h-1.5 rounded-full bg-current"></span>
    {method}
  </span>
);

export const TypeBadge: React.FC<{ type: string }> = ({ type }) => (
  <span
    className={`px-space-xs py-0.5 rounded font-label-sm text-label-sm font-semibold font-mono ${
      type === 'legal' ? 'bg-surface-container-high text-primary' : 'bg-tertiary-fixed text-on-tertiary-container'
    }`}
  >
    {type}
  </span>
);

export const ScoreBar: React.FC<{ value: number; max?: number; threshold?: number }> = ({ value, max = 1, threshold }) => (
  <div className="relative h-1.5 rounded-full bg-surface-container overflow-hidden">
    <div
      className="absolute inset-y-0 left-0 bg-secondary rounded-full"
      style={{ width: `${Math.max(0, Math.min(100, (value / max) * 100))}%` }}
    ></div>
    {threshold !== undefined && (
      <div className="absolute inset-y-0 w-0.5 bg-error" style={{ left: `${(threshold / max) * 100}%` }}></div>
    )}
  </div>
);

/** Hiển thị câu trả lời LLM: bullet "- ", **bold** và citation [n] bấm được. */
export const AnswerText: React.FC<{ text: string; onCite?: (n: number) => void; maxCite?: number }> = ({
  text,
  onCite,
  maxCite = Infinity,
}) => {
  const renderInline = (line: string, key: string) =>
    line.split(/(\[\d+\]|\*\*[^*]+\*\*)/g).map((part, index) => {
      const cite = part.match(/^\[(\d+)\]$/);
      if (cite && Number(cite[1]) <= maxCite) {
        const n = Number(cite[1]);
        return (
          <button
            key={`${key}-${index}`}
            type="button"
            onClick={() => onCite?.(n)}
            className="inline-flex items-center px-1.5 mx-0.5 rounded font-label-sm text-label-sm font-bold bg-amber-100 text-amber-900 hover:bg-amber-200 border border-amber-300 cursor-pointer"
          >
            [{n}]
          </button>
        );
      }
      if (part.startsWith('**') && part.endsWith('**')) return <strong key={`${key}-${index}`}>{part.slice(2, -2)}</strong>;
      return <React.Fragment key={`${key}-${index}`}>{part}</React.Fragment>;
    });

  const blocks: React.ReactNode[] = [];
  let bullets: string[] = [];
  const flush = () => {
    if (bullets.length) {
      const items = bullets;
      blocks.push(
        <ul key={`ul-${blocks.length}`} className="list-disc pl-5 space-y-1">
          {items.map((item, i) => (
            <li key={i}>{renderInline(item, `li-${blocks.length}-${i}`)}</li>
          ))}
        </ul>,
      );
      bullets = [];
    }
  };
  text.split('\n').forEach((raw, i) => {
    const line = raw.trim();
    const bullet = line.match(/^(?:[-*•]|\d+\.)\s+(.*)$/);
    if (bullet) {
      bullets.push(bullet[1]);
      return;
    }
    flush();
    if (line) blocks.push(<p key={`p-${i}`}>{renderInline(line.replace(/^#+\s*/, ''), `p-${i}`)}</p>);
  });
  flush();
  return <div className="font-body-md text-body-md text-on-surface leading-relaxed space-y-space-sm">{blocks}</div>;
};
