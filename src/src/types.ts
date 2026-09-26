export type PageTab =
  | 'tro-chuyen'
  | 'pipeline-realtime'
  | 'xep-hang'
  | 'danh-gia-ab'
  | 'kho-du-lieu'
  | 'cau-hinh';

export interface SourceChunk {
  id: string;
  chunkNumber: number;
  title: string;
  type: 'legal' | 'news';
  method: 'hybrid' | 'dense' | 'bm25' | 'pageindex';
  similarity: number;
  snippet: string;
  highlightedSnippet?: string;
  fullContent?: string;
  docId: string;
  docName: string;
  docPath?: string;
  isCited: boolean;
  tokensCount?: number;
  charCount?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  senderName: string;
  retrievalStrategy?: 'hybrid' | 'dense';
  statusBadge?: string;
  sourcesCount?: number;
  latencySec?: number;
  tokensCount?: number;
  sources?: SourceChunk[];
  tableSummary?: {
    time: string;
    description: string;
  }[];
  isRefusal?: boolean;
  refusalReason?: string;
  rewriteNote?: string;
}

export interface PipelineStage {
  id: string;
  num: string;
  name: string;
  duration: string;
  durationMs: number;
  status: 'success' | 'skip' | 'fallback';
  subtext: string;
  title: string;
  description: string;
  metrics?: Record<string, string | number>;
}

export interface DocumentItem {
  id: string;
  docId: string;
  title: string;
  fileType: 'PDF' | 'DOCX' | 'URL' | 'ERR';
  category: 'legal' | 'news';
  sourceFile: string;
  size: string;
  chunksCount: number;
  status: 'indexed' | 'ocr_needed';
  lastModified: string;
}

export interface SystemConfig {
  llmProvider: 'openai' | 'gemini' | 'claude';
  llmModel: string;
  temperature: number;
  topP: number;
  embeddingModel: string;
  retrievalStrategy: 'hybrid' | 'dense';
  topK: number;
  candidatesPerRetriever: number;
  rrfK: number;
  cosineCutoff: number;
  pageIndexFallback: boolean;
  enableHyDE: boolean;
  enableQueryExpansion: boolean;
  enableReranker: boolean;
  rerankerModel: string;
  enableConversationMemory: boolean;
  enableGoldHighlight: boolean;
}
