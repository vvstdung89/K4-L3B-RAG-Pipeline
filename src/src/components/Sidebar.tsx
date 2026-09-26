import React from 'react';
import { PageTab } from '../types';
import { api, fmtMs, useApi } from '../api';

interface SidebarProps {
  activeTab: PageTab;
  setActiveTab: (tab: PageTab) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab }) => {
  const evaluation = useApi('evaluation', api.evaluation);
  const configs = evaluation.data?.summary?.configs ?? {};
  const best = configs.B_hybrid_rrf ?? Object.values(configs)[0];
  const navItems: { id: PageTab; label: string; icon: string }[] = [
    { id: 'tro-chuyen', label: 'Trò chuyện', icon: 'chat' },
    { id: 'pipeline-realtime', label: 'Pipeline realtime', icon: 'account_tree' },
    { id: 'xep-hang', label: 'Xếp hạng', icon: 'leaderboard' },
    { id: 'danh-gia-ab', label: 'Đánh giá A/B', icon: 'compare_arrows' },
    { id: 'kho-du-lieu', label: 'Kho dữ liệu', icon: 'dataset' },
    { id: 'cau-hinh', label: 'Cấu hình', icon: 'tune' },
  ];

  return (
    <aside className="fixed left-0 top-0 h-full w-64 bg-surface-container-lowest shadow-[0_1px_8px_rgba(0,0,0,0.04)] z-50 flex flex-col justify-between py-space-lg border-r border-slate-200/60">
      <div className="px-space-md">
        {/* Brand Logo & Title */}
        <div
          onClick={() => setActiveTab('tro-chuyen')}
          className="flex items-center gap-space-sm px-space-sm mb-space-xl cursor-pointer group"
        >
          <div className="w-9 h-9 rounded-lg bg-primary-container text-secondary-container flex items-center justify-center shadow-xs group-hover:scale-105 transition-transform">
                        <svg viewBox="0 0 24 24" className="w-6 h-6" fill="currentColor">
              <path d="M12 2L4 16h16L12 2zm0 4.2l4.8 8.8H7.2L12 6.2z" fill="#79f3e8" />
              <circle cx="12" cy="11.5" r="2.5" fill="#f9bd14" />
              <path d="M6 18.5c2.5-1 9.5-1 12 0v1.5c-2.5-1-9.5-1-12 0v-1.5z" fill="#ffffff" />
            </svg>
          </div>
          <div>
            <div className="font-headline-sm text-headline-sm text-primary tracking-tight font-bold">
              Du Lịch Việt RAG
            </div>
            <div className="font-label-sm text-label-sm text-on-surface-variant truncate">
              Luật · Visa · Điểm đến
            </div>
          </div>
        </div>

        {/* Navigation list */}
        <nav className="flex flex-col gap-space-xs">
          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => setActiveTab(item.id)}
                className={`flex items-center gap-space-sm px-space-md py-space-sm rounded-lg transition-all text-left w-full cursor-pointer ${
                  isActive
                    ? 'bg-primary-container text-on-primary font-headline-sm shadow-sm'
                    : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
                }`}
              >
                <span className="material-symbols-outlined text-[20px]">
                  {item.icon}
                </span>
                <span className="font-body-md text-body-md">{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Engine Status Bottom Tile */}
      <div className="px-space-md">
        <div className="bg-surface-container-low rounded-xl p-space-sm flex flex-col gap-space-xs border border-slate-200/50">
          <div className="flex items-center justify-between text-on-surface-variant">
            <span className="font-label-sm text-label-sm uppercase tracking-wider font-semibold">
              Đánh giá gần nhất
            </span>
            <span className="font-label-sm text-label-sm text-secondary font-bold">
              {evaluation.data?.summary?.evaluation_date ?? '—'}
            </span>
          </div>
          <div className="flex items-center justify-between font-label-sm text-label-sm text-on-surface-variant">
            <span>Latency TB (hybrid)</span>
            <span className="font-label-sm text-label-sm text-primary font-semibold">
              {best ? fmtMs(best.latency_ms_mean) : '—'}
            </span>
          </div>
          <div className="flex items-center justify-between font-label-sm text-label-sm text-on-surface-variant">
            <span>Faithfulness</span>
            <span className="font-label-sm text-label-sm text-on-tertiary-container font-bold">
              {best?.faithfulness != null ? best.faithfulness.toFixed(3) : '—'}
            </span>
          </div>
        </div>
      </div>
    </aside>
  );
};
