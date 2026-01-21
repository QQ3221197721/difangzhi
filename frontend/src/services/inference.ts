/**
 * 地方志数据智能管理系统 - 推理服务
 * 与后端AI/RAG接口交互
 */

import { apiClient } from './api';

// ==================== 类型定义 ====================

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface ChatRequest {
  message: string;
  history?: ChatMessage[];
  stream?: boolean;
}

export interface ChatResponse {
  content: string;
  tokens_used: number;
  sources?: SearchSource[];
}

export interface SearchSource {
  id: number;
  title: string;
  content: string;
  score: number;
  region?: string;
  year?: number;
}

export interface SemanticSearchRequest {
  query: string;
  top_k?: number;
  filters?: {
    region?: string;
    year_from?: number;
    year_to?: number;
    category?: string;
  };
}

export interface SemanticSearchResponse {
  answer: string;
  sources: SearchSource[];
  confidence: number;
}

export interface SummarizeRequest {
  content: string;
  max_length?: number;
}

export interface SummarizeResponse {
  summary: string;
  keywords: string[];
}

export interface EmbeddingRequest {
  texts: string[];
}

export interface EmbeddingResponse {
  embeddings: number[][];
  model: string;
  dimension: number;
}

export interface ModelInfo {
  name: string;
  type: string;
  status: 'not_downloaded' | 'downloading' | 'downloaded' | 'loaded' | 'error';
  size_mb: number;
  description?: string;
}

// ==================== AI聊天服务 ====================

/**
 * AI对话
 */
export async function chat(request: ChatRequest): Promise<ChatResponse> {
  const response = await apiClient.post<ChatResponse>('/api/ai/chat', request);
  return response.data;
}

/**
 * 流式AI对话
 */
export async function* streamChat(request: ChatRequest): AsyncGenerator<string> {
  const response = await fetch('/api/ai/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${localStorage.getItem('token')}`,
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }

  const decoder = new TextDecoder();
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value, { stream: true });
    const lines = chunk.split('\n');
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') return;
        try {
          const parsed = JSON.parse(data);
          if (parsed.content) {
            yield parsed.content;
          }
        } catch {
          yield data;
        }
      }
    }
  }
}

// ==================== 语义搜索服务 ====================

/**
 * 语义搜索
 */
export async function semanticSearch(
  request: SemanticSearchRequest
): Promise<SemanticSearchResponse> {
  const response = await apiClient.post<SemanticSearchResponse>(
    '/api/ai/search',
    request
  );
  return response.data;
}

/**
 * RAG问答
 */
export async function ragQuery(
  question: string,
  filters?: SemanticSearchRequest['filters']
): Promise<SemanticSearchResponse> {
  const response = await apiClient.post<SemanticSearchResponse>(
    '/api/ai/rag/query',
    { question, filters }
  );
  return response.data;
}

// ==================== 文档处理服务 ====================

/**
 * 生成摘要
 */
export async function summarize(
  request: SummarizeRequest
): Promise<SummarizeResponse> {
  const response = await apiClient.post<SummarizeResponse>(
    '/api/ai/summarize',
    request
  );
  return response.data;
}

/**
 * 提取关键词
 */
export async function extractKeywords(content: string): Promise<string[]> {
  const response = await apiClient.post<{ keywords: string[] }>(
    '/api/ai/keywords',
    { content }
  );
  return response.data.keywords;
}

/**
 * 批量AI处理文档
 */
export async function batchProcess(
  documentIds: number[],
  operations: ('summarize' | 'keywords' | 'embedding')[]
): Promise<{ task_id: string }> {
  const response = await apiClient.post<{ task_id: string }>(
    '/api/ai/batch-process',
    { document_ids: documentIds, operations }
  );
  return response.data;
}

// ==================== 嵌入服务 ====================

/**
 * 生成文本嵌入
 */
export async function getEmbeddings(
  request: EmbeddingRequest
): Promise<EmbeddingResponse> {
  const response = await apiClient.post<EmbeddingResponse>(
    '/api/ai/embeddings',
    request
  );
  return response.data;
}

/**
 * 计算文本相似度
 */
export async function computeSimilarity(
  text1: string,
  text2: string
): Promise<{ similarity: number }> {
  const response = await apiClient.post<{ similarity: number }>(
    '/api/ai/similarity',
    { text1, text2 }
  );
  return response.data;
}

// ==================== 模型管理服务 ====================

/**
 * 获取模型列表
 */
export async function listModels(type?: string): Promise<ModelInfo[]> {
  const params = type ? { type } : {};
  const response = await apiClient.get<ModelInfo[]>('/api/ai/models', { params });
  return response.data;
}

/**
 * 下载模型
 */
export async function downloadModel(name: string): Promise<{ task_id: string }> {
  const response = await apiClient.post<{ task_id: string }>(
    `/api/ai/models/${name}/download`
  );
  return response.data;
}

/**
 * 加载模型
 */
export async function loadModel(name: string): Promise<{ success: boolean }> {
  const response = await apiClient.post<{ success: boolean }>(
    `/api/ai/models/${name}/load`
  );
  return response.data;
}

/**
 * 卸载模型
 */
export async function unloadModel(name: string): Promise<{ success: boolean }> {
  const response = await apiClient.post<{ success: boolean }>(
    `/api/ai/models/${name}/unload`
  );
  return response.data;
}

// ==================== 健康检查 ====================

/**
 * AI服务健康检查
 */
export async function healthCheck(): Promise<{
  status: string;
  inference_engine: boolean;
  embedding_service: boolean;
  vector_store: boolean;
}> {
  const response = await apiClient.get('/api/ai/health');
  return response.data;
}

// ==================== 导出服务对象 ====================

export const inferenceService = {
  // 聊天
  chat,
  streamChat,
  // 搜索
  semanticSearch,
  ragQuery,
  // 文档处理
  summarize,
  extractKeywords,
  batchProcess,
  // 嵌入
  getEmbeddings,
  computeSimilarity,
  // 模型管理
  listModels,
  downloadModel,
  loadModel,
  unloadModel,
  // 健康检查
  healthCheck,
};

export default inferenceService;
