import { useEffect, useState } from 'react';

export type RetrievalMethod = 'dense' | 'bm25' | 'hybrid' | 'pageindex';

export interface AppConfig {
  llm_provider: string;
  llm_model: string;
  temperature: number;
  top_p: number;
  top_k: number;
  candidate_multiplier: number;
  rrf_k: number;
  score_threshold: number;
  embedding_provider: string;
  embedding_model: string;
  embedding_dim: number;
  chunk_size: number;
  chunk_overlap: number;
  chunking_method: string;
  collection_name: string;
  collection_count: number;
  distance: string;
  pageindex_configured: boolean;
  api_keys: Record<string, boolean>;
  system_prompt: string;
  refusal_message: string;
}

export interface DocumentInfo {
  id: string;
  title: string;
  doc_type: 'legal' | 'news';
  source: string;
  url: string | null;
  landing_file: string | null;
  landing_format: string | null;
  landing_bytes: number | null;
  markdown_chars: number;
  markdown_bytes: number;
  chunks: number;
  modified: string;
}

export interface DocumentsResponse {
  documents: DocumentInfo[];
  total_chunks: number;
  orphan_chunks: number;
  avg_chunk_chars: number;
}

export interface ChunkRecord {
  id: string;
  content: string;
  chars: number;
  metadata: { title: string; source: string; doc_type: string; url: string | null; chunk_index: number };
}

export interface RankedChunk {
  rank: number;
  id: string;
  score: number;
  retrieval_method: RetrievalMethod;
  title: string;
  source: string;
  doc_type: string;
  url: string | null;
  chunk_index: number;
  content: string;
  dense_rank?: number | null;
  bm25_rank?: number | null;
  dense_score?: number | null;
  cited?: boolean;
}

export interface RetrievalTrace {
  query: string;
  top_k: number;
  use_reranking: boolean;
  score_threshold: number;
  best_dense_score: number;
  dense: RankedChunk[];
  bm25: RankedChunk[];
  final: RankedChunk[];
  retrieval_source: RetrievalMethod | 'none';
  fallback: { triggered: boolean; configured: boolean; used: boolean; error: string | null };
  timings: Record<string, number>;
}

export interface ChatResult extends RetrievalTrace {
  answer: string;
  refused: boolean;
  cited: number[];
  sources: RankedChunk[];
  generator: string;
  error: string | null;
  timestamp: string;
}

export interface EvalMetrics {
  faithfulness: number | null;
  answer_relevancy: number | null;
  context_recall: number | null;
  context_precision: number | null;
  average: number | null;
  refusals: number;
  source_hit_rate: number;
  latency_ms_mean: number;
  retrieval_ms_mean: number;
}

export interface EvalRow {
  question: string;
  answer: string;
  refused: boolean;
  source_ids: string[];
  retrieval_method: string;
  expected_answer: string;
  expected_source: string;
  hit_expected_source: boolean;
  latency_ms: number;
  retrieval_ms: number;
  faithfulness: number | null;
  answer_relevancy: number | null;
  context_recall: number | null;
  context_precision: number | null;
}

export interface EvaluationResponse {
  summary: {
    evaluation_date: string;
    golden_size: number;
    top_k: number;
    generator: string;
    evaluator: string;
    evaluator_embedding: string;
    calibration?: {
      configured_threshold: number;
      in_domain: { min: number; mean: number; max: number };
      out_of_domain: { min: number; mean: number; max: number };
      in_domain_below_threshold: number;
      out_of_domain_scores: Record<string, number>;
    };
    configs: Record<string, EvalMetrics>;
  } | null;
  runs: Record<string, EvalRow[]>;
  golden: { question: string; expected_answer: string; source?: string }[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      // body không phải JSON
    }
    throw new Error(detail);
  }
  const type = response.headers.get('content-type') || '';
  return (type.includes('application/json') ? response.json() : response.text()) as Promise<T>;
}

const postJson = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export const api = {
  config: () => request<AppConfig>('/api/config'),
  documents: () => request<DocumentsResponse>('/api/documents'),
  chunks: (docId: string) =>
    request<{ doc_id: string; chunks: ChunkRecord[] }>(`/api/documents/chunks?doc_id=${encodeURIComponent(docId)}`),
  markdownUrl: (docId: string) => `/api/documents/markdown?doc_id=${encodeURIComponent(docId)}`,
  evaluation: () => request<EvaluationResponse>('/api/evaluation'),
  retrieve: (query: string, topK: number, useReranking: boolean) =>
    postJson<RetrievalTrace>('/api/retrieve', { query, top_k: topK, use_reranking: useReranking }),
  chat: (query: string, topK: number, useReranking: boolean) =>
    postJson<ChatResult>('/api/chat', { query, top_k: topK, use_reranking: useReranking }),
};

// Cache theo key để chuyển tab không gọi lại API.
const cache = new Map<string, Promise<unknown>>();

export function useApi<T>(key: string, loader: () => Promise<T>) {
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({
    data: null,
    error: null,
    loading: true,
  });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let alive = true;
    if (!cache.has(key)) cache.set(key, loader());
    (cache.get(key) as Promise<T>)
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch((error: Error) => {
        cache.delete(key);
        if (alive) setState({ data: null, error: error.message, loading: false });
      });
    return () => {
      alive = false;
    };
  }, [key, version]);

  const reload = () => {
    cache.delete(key);
    setState((prev) => ({ ...prev, loading: true }));
    setVersion((v) => v + 1);
  };
  return { ...state, reload };
}

export const fmtScore = (value: number | null | undefined, digits = 3) =>
  value === null || value === undefined ? '—' : value.toFixed(digits);

export const fmtBytes = (bytes: number | null | undefined) => {
  if (bytes === null || bytes === undefined) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
};

export const fmtMs = (ms: number | undefined) =>
  ms === undefined ? '—' : ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${Math.round(ms)} ms`;
