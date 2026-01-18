// 地方志系统 - TypeScript 类型定义

// 用户相关
export interface User {
  id: number;
  username: string;
  email: string;
  real_name: string;
  phone?: string;
  role: 'admin' | 'editor' | 'viewer' | 'uploader';
  is_active: boolean;
  is_verified: boolean;
  avatar_url?: string;
  last_login?: string;
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
  location?: {
    latitude: number;
    longitude: number;
  };
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

// 文档相关
export type DataStatus = 'pending' | 'approved' | 'rejected' | 'archived';

export interface Document {
  id: number;
  title: string;
  content?: string;
  full_text?: string;
  source?: string;
  author?: string;
  publish_date?: string;
  file_path?: string;
  file_name?: string;
  file_size?: number;
  file_type?: string;
  region?: string;
  year?: number;
  tags: string[];
  ai_summary?: string;
  ai_keywords?: string[];
  status: DataStatus;
  upload_type: 'file' | 'manual';
  uploader_id: number;
  view_count: number;
  download_count: number;
  created_at: string;
  updated_at: string;
  categories: Category[];
}

export interface DocumentCreate {
  title: string;
  content?: string;
  source?: string;
  author?: string;
  region?: string;
  year?: number;
  tags?: string[];
  category_ids?: number[];
  publish_date?: string;
}

// 分类相关
export interface Category {
  id: number;
  name: string;
  code: string;
  level: number;
  parent_id?: number;
  category_type: string;
  description?: string;
  sort_order: number;
  is_active: boolean;
  created_at: string;
  children?: Category[];
}

// 搜索相关
export interface SearchQuery {
  keyword?: string;
  region?: string;
  year_start?: number;
  year_end?: number;
  category_ids?: number[];
  tags?: string[];
  status?: DataStatus;
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface SearchResult {
  documents: Document[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  keywords?: string[];
}

export interface AISearchQuery {
  question: string;
  top_k?: number;
}

export interface AISearchResult {
  answer: string;
  sources: Document[];
  confidence: number;
}

// 聊天相关
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at?: string;
}

export interface ChatRequest {
  content: string;
  session_id?: string;
}

export interface ChatResponse {
  session_id: string;
  content: string;
  tokens_used: number;
  created_at: string;
}

// 数据分析
export interface AnalyticsOverview {
  documents: {
    total: number;
    pending: number;
    approved: number;
  };
  users: {
    total: number;
    active: number;
  };
  categories: number;
  upload_trend: { date: string; count: number }[];
}

export interface AnalyticsResult {
  metric: string;
  data: Record<string, any>[];
  chart_type: 'bar' | 'line' | 'pie' | 'area';
  summary: Record<string, any>;
}

// API 响应
export interface ApiResponse<T = any> {
  code: number;
  message: string;
  data?: T;
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  total: number;
  page: number;
  page_size: number;
  pages: number;
}
