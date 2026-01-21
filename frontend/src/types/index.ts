/**
 * 地方志数据智能管理系统 - 类型定义
 */

// ==================== 通用类型 ====================

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export interface ErrorResponse {
  code: number;
  message: string;
  detail?: string;
}

// ==================== 用户相关 ====================

export interface User {
  id: number;
  username: string;
  email: string;
  full_name?: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  last_login?: string;
  avatar?: string;
}

export type UserRole = 'admin' | 'editor' | 'viewer';

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  full_name?: string;
}

// ==================== 文档相关 ====================

export interface Document {
  id: number;
  title: string;
  content?: string;
  region?: string;
  year?: number;
  tags?: string[];
  source?: string;
  author?: string;
  category_id?: number;
  category?: Category;
  status: DocumentStatus;
  ai_summary?: string;
  ai_keywords?: string[];
  file_path?: string;
  file_type?: string;
  file_size?: number;
  created_at: string;
  updated_at: string;
  created_by?: number;
  creator?: User;
}

export type DocumentStatus = 'draft' | 'pending' | 'approved' | 'rejected' | 'archived';

export interface DocumentCreateRequest {
  title: string;
  content?: string;
  region?: string;
  year?: number;
  tags?: string[];
  source?: string;
  author?: string;
  category_id?: number;
}

export interface DocumentUpdateRequest extends Partial<DocumentCreateRequest> {
  status?: DocumentStatus;
}

export interface DocumentFilter {
  keyword?: string;
  status?: DocumentStatus;
  region?: string;
  year_from?: number;
  year_to?: number;
  category_id?: number;
  tags?: string[];
  created_by?: number;
}

// ==================== 分类相关 ====================

export interface Category {
  id: number;
  name: string;
  code: string;
  level: number;
  parent_id?: number;
  parent?: Category;
  children?: Category[];
  category_type: CategoryType;
  description?: string;
  sort_order: number;
  document_count?: number;
}

export type CategoryType = 'region' | 'theme' | 'era' | 'custom';

export interface CategoryCreateRequest {
  name: string;
  code: string;
  parent_id?: number;
  category_type: CategoryType;
  description?: string;
  sort_order?: number;
}

// ==================== 统计相关 ====================

export interface DashboardStats {
  total_documents: number;
  pending_documents: number;
  approved_documents: number;
  total_users: number;
  storage_used_mb: number;
  ai_queries_today: number;
}

export interface DocumentStats {
  by_status: Record<DocumentStatus, number>;
  by_region: { region: string; count: number }[];
  by_year: { year: number; count: number }[];
  by_category: { category: string; count: number }[];
  recent_uploads: { date: string; count: number }[];
}

export interface UserActivity {
  user_id: number;
  username: string;
  action: string;
  target_type: string;
  target_id: number;
  timestamp: string;
  details?: Record<string, unknown>;
}

// ==================== AI相关 ====================

export interface ChatMessage {
  id?: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
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

export interface RAGResponse {
  answer: string;
  sources: SearchSource[];
  confidence: number;
  tokens_used?: number;
}

// ==================== 文件上传 ====================

export interface UploadProgress {
  filename: string;
  progress: number;
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'error';
  error?: string;
  document_id?: number;
}

export interface FileInfo {
  name: string;
  size: number;
  type: string;
  lastModified: number;
}

// ==================== 任务相关 ====================

export interface AsyncTask {
  id: string;
  type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  result?: unknown;
  error?: string;
  created_at: string;
  updated_at: string;
}

// ==================== 通知相关 ====================

export interface Notification {
  id: number;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  read: boolean;
  created_at: string;
  action_url?: string;
}

// ==================== 系统配置 ====================

export interface SystemConfig {
  site_name: string;
  site_logo?: string;
  ai_enabled: boolean;
  max_upload_size_mb: number;
  allowed_file_types: string[];
  default_language: string;
}

// ==================== 权限相关 ====================

export interface Permission {
  resource: string;
  actions: ('create' | 'read' | 'update' | 'delete')[];
}

export interface RolePermissions {
  role: UserRole;
  permissions: Permission[];
}

// ==================== 表单验证 ====================

export interface ValidationError {
  field: string;
  message: string;
}

export interface FormState<T> {
  values: T;
  errors: Record<string, string>;
  touched: Record<string, boolean>;
  isSubmitting: boolean;
  isValid: boolean;
}

// ==================== 表格相关 ====================

export interface TableColumn<T> {
  key: keyof T | string;
  title: string;
  width?: number;
  sortable?: boolean;
  render?: (value: unknown, record: T, index: number) => React.ReactNode;
}

export interface SortState {
  field: string;
  order: 'asc' | 'desc';
}

export interface PaginationState {
  page: number;
  size: number;
  total: number;
}
