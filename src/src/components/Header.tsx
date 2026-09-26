import React, { useState } from 'react';
import { api, useApi } from '../api';

interface HeaderProps {
  onOpenSettings?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onOpenSettings }) => {
  const [showHelpModal, setShowHelpModal] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const config = useApi('config', api.config);
  const c = config.data;

  const toggleTheme = () => {
    setIsDarkMode(!isDarkMode);
    document.documentElement.classList.toggle('dark');
  };

  return (
    <>
      <header className="fixed top-0 left-64 right-0 h-16 bg-surface/90 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.04)] z-40 flex items-center justify-between px-gutter border-b border-slate-200/60">
        {/* Left Telemetry Cluster */}
        <div className="flex items-center gap-space-md overflow-x-auto py-1">
          <div className="flex items-center gap-space-xs bg-surface-container-low px-space-sm py-space-xs rounded-full border border-slate-200/50">
            <span className="font-label-sm text-label-sm text-on-surface-variant uppercase font-semibold">
              LLM
            </span>
            <span className="font-label-sm text-label-sm text-primary font-bold">
              {c ? `${c.llm_provider}/${c.llm_model}` : '…'}
            </span>
          </div>

          <div className="flex items-center gap-space-xs bg-surface-container-low px-space-sm py-space-xs rounded-full border border-slate-200/50">
            <span className="font-label-sm text-label-sm text-on-surface-variant uppercase font-semibold">
              Embed
            </span>
            <span className="font-label-sm text-label-sm text-secondary font-bold">
              {c?.embedding_model ?? '…'}
            </span>
          </div>

          <div className="flex items-center gap-space-xs bg-surface-container px-space-sm py-space-xs rounded-full border border-slate-200/50">
            <span className={`w-2 h-2 rounded-full ${config.error ? 'bg-error' : 'bg-secondary animate-pulse'}`}></span>
            <span className="font-label-sm text-label-sm text-on-surface font-medium">
              {config.error
                ? 'Backend chưa chạy'
                : c
                  ? `ChromaDB: ${c.collection_name} — ${c.collection_count} vectors`
                  : 'Đang kết nối…'}
            </span>
          </div>
        </div>

        {/* Right Action Controls */}
        <div className="flex items-center gap-space-sm flex-shrink-0">
          <button
            type="button"
            onClick={() => setShowHelpModal(true)}
            className="w-9 h-9 rounded-lg bg-surface-container-low hover:bg-surface-container text-on-surface-variant hover:text-on-surface flex items-center justify-center transition-colors cursor-pointer"
            title="Tài liệu hỗ trợ & Hướng dẫn RAG"
          >
            <span className="material-symbols-outlined text-[20px]">help_outline</span>
          </button>

          <button
            type="button"
            onClick={toggleTheme}
            className="w-9 h-9 rounded-lg bg-surface-container-low hover:bg-surface-container text-on-surface-variant hover:text-on-surface flex items-center justify-center transition-colors cursor-pointer"
            title={isDarkMode ? "Chuyển sang giao diện sáng" : "Chuyển sang giao diện tối"}
          >
            <span className="material-symbols-outlined text-[20px]">
              {isDarkMode ? 'dark_mode' : 'light_mode'}
            </span>
          </button>

          <div className="h-5 w-px bg-outline-variant mx-space-xs"></div>

          <button
            type="button"
            onClick={onOpenSettings}
            className="w-8 h-8 rounded-full bg-primary flex items-center justify-center cursor-pointer shadow-xs hover:ring-2 hover:ring-secondary/50 transition-all"
            title="Hồ sơ quản trị viên"
          >
            <span className="material-symbols-outlined text-on-primary text-[18px]">person</span>
          </button>
        </div>
      </header>

      {/* Quick Help Modal */}
      {showHelpModal && (
        <div
          className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4"
          onClick={() => setShowHelpModal(false)}
        >
          <div
            className="bg-surface-container-lowest rounded-xl max-w-lg w-full p-6 shadow-2xl flex flex-col gap-4 border border-slate-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-primary-container text-secondary-container flex items-center justify-center">
                  <span className="material-symbols-outlined text-[20px]">travel_explore</span>
                </div>
                <h3 className="font-headline-sm text-headline-sm text-primary">
                  Về Du Lịch Việt RAG
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowHelpModal(false)}
                className="w-8 h-8 rounded-lg hover:bg-surface-container flex items-center justify-center text-on-surface-variant"
              >
                <span className="material-symbols-outlined text-[20px]">close</span>
              </button>
            </div>

            <div className="space-y-3 font-body-sm text-body-sm text-on-surface-variant leading-relaxed">
              <p>
                <strong className="text-primary font-semibold">Du Lịch Việt RAG</strong> tra cứu Luật Du lịch 2017, thông tin visa/nhập cảnh và cẩm nang điểm đến Việt Nam từ các tài liệu trong thư mục <code>data/</code>.
              </p>
              <div className="bg-surface-container-low p-3 rounded-lg flex flex-col gap-1.5 font-label-sm text-label-sm text-on-surface">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-secondary"></span>
                  <span><strong>Hybrid Retrieval:</strong> Kết hợp Dense Vector Cosine + Từ khóa chuẩn BM25.</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-secondary"></span>
                  <span><strong>RRF Fusion (k=60):</strong> Chống thiên vị văn bản ngắn, ưu tiên điều lệ chính xác.</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-secondary"></span>
                  <span><strong>Chống ảo giác (ngưỡng cosine {c?.score_threshold ?? '…'}):</strong> Tự động từ chối an toàn khi ngoài phạm vi.</span>
                </div>
              </div>
              <p>
                Mọi thông tin trích dẫn đều gắn kèm nhãn anchor citation <span className="bg-amber-100 text-amber-900 font-bold px-1.5 py-0.5 rounded text-xs">[1]</span> để đối chiếu trực tiếp với văn bản gốc.
              </p>
            </div>

            <div className="flex justify-end pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setShowHelpModal(false)}
                className="px-4 py-2 bg-primary text-on-primary rounded-lg font-headline-sm text-[13px] hover:bg-primary-container transition-colors shadow-sm"
              >
                Đã hiểu
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
