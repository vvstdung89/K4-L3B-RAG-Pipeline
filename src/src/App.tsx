import React, { useState } from 'react';
import { PageTab } from './types';
import { ChatResult } from './api';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { ChatView, ChatTurn } from './views/ChatView';
import { PipelineView } from './views/PipelineView';
import { RankingView } from './views/RankingView';
import { EvaluationView } from './views/EvaluationView';
import { DatasetView } from './views/DatasetView';
import { SettingsView } from './views/SettingsView';

export default function App() {
  const [activeTab, setActiveTab] = useState<PageTab>('tro-chuyen');
  // Giữ hội thoại ở App để chuyển tab không mất; Pipeline/Xếp hạng dùng lượt hỏi gần nhất.
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const lastResult: ChatResult | null =
    [...turns].reverse().find((turn) => turn.result)?.result ?? null;

  return (
    <div className="min-h-screen bg-surface font-body-md text-body-md text-on-surface">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />

      <div className="pl-64 flex flex-col min-h-screen">
        <Header onOpenSettings={() => setActiveTab('cau-hinh')} />

        <main className="relative pt-16 bg-surface min-h-screen px-gutter py-space-lg">
          <div className="max-w-[1440px] mx-auto w-full pt-space-lg">
            {activeTab === 'tro-chuyen' && <ChatView turns={turns} setTurns={setTurns} onNavigate={setActiveTab} />}
            {activeTab === 'pipeline-realtime' && <PipelineView result={lastResult} onNavigate={setActiveTab} />}
            {activeTab === 'xep-hang' && <RankingView initialQuery={lastResult?.query} />}
            {activeTab === 'danh-gia-ab' && <EvaluationView />}
            {activeTab === 'kho-du-lieu' && <DatasetView />}
            {activeTab === 'cau-hinh' && <SettingsView />}
          </div>
        </main>
      </div>
    </div>
  );
}
