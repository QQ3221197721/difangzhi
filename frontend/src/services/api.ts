/**
 * 地方志数据智能管理系统 - API服务
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';

// API基础配置
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// 创建axios实例
export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // 处理401错误 - token过期
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        try {
          const response = await axios.post(`${API_BASE_URL}/api/auth/refresh`, {
            refresh_token: refreshToken,
          });
          
          const { access_token } = response.data;
          localStorage.setItem('token', access_token);
          
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return apiClient(originalRequest);
        } catch (refreshError) {
          // 刷新token失败，清除登录状态
          localStorage.removeItem('token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login';
        }
      }
    }
    
    return Promise.reject(error);
  }
);

// ==================== 通用请求方法 ====================

export async function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const response: AxiosResponse<T> = await apiClient.get(url, config);
  return response.data;
}

export async function post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  const response: AxiosResponse<T> = await apiClient.post(url, data, config);
  return response.data;
}

export async function put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  const response: AxiosResponse<T> = await apiClient.put(url, data, config);
  return response.data;
}

export async function del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const response: AxiosResponse<T> = await apiClient.delete(url, config);
  return response.data;
}

// ==================== 认证服务 ====================

export const authService = {
  login: async (username: string, password: string) => {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    return post<{ access_token: string; refresh_token: string; user: unknown }>(
      '/api/auth/login',
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
  },
  
  register: async (data: { username: string; email: string; password: string; full_name?: string }) => {
    return post('/api/auth/register', data);
  },
  
  logout: async () => {
    return post('/api/auth/logout');
  },
  
  getCurrentUser: async () => {
    return get('/api/auth/me');
  },
  
  refreshToken: async (refreshToken: string) => {
    return post('/api/auth/refresh', { refresh_token: refreshToken });
  },
};

// ==================== 文档服务 ====================

export const documentService = {
  list: async (params?: {
    page?: number;
    size?: number;
    keyword?: string;
    status?: string;
    region?: string;
    category_id?: number;
  }) => {
    return get('/api/documents', { params });
  },
  
  getById: async (id: number) => {
    return get(`/api/documents/${id}`);
  },
  
  create: async (data: unknown) => {
    return post('/api/documents', data);
  },
  
  update: async (id: number, data: unknown) => {
    return put(`/api/documents/${id}`, data);
  },
  
  delete: async (id: number) => {
    return del(`/api/documents/${id}`);
  },
  
  upload: async (file: File, metadata?: unknown) => {
    const formData = new FormData();
    formData.append('file', file);
    if (metadata) {
      formData.append('metadata', JSON.stringify(metadata));
    }
    return post('/api/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  
  batchUpload: async (files: File[]) => {
    const formData = new FormData();
    files.forEach((file) => formData.append('files', file));
    return post('/api/documents/batch-upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  
  approve: async (id: number) => {
    return post(`/api/documents/${id}/approve`);
  },
  
  reject: async (id: number, reason?: string) => {
    return post(`/api/documents/${id}/reject`, { reason });
  },
};

// ==================== 分类服务 ====================

export const categoryService = {
  list: async (type?: string) => {
    return get('/api/categories', { params: { type } });
  },
  
  getTree: async (type?: string) => {
    return get('/api/categories/tree', { params: { type } });
  },
  
  getById: async (id: number) => {
    return get(`/api/categories/${id}`);
  },
  
  create: async (data: unknown) => {
    return post('/api/categories', data);
  },
  
  update: async (id: number, data: unknown) => {
    return put(`/api/categories/${id}`, data);
  },
  
  delete: async (id: number) => {
    return del(`/api/categories/${id}`);
  },
};

// ==================== 用户服务 ====================

export const userService = {
  list: async (params?: { page?: number; size?: number; keyword?: string }) => {
    return get('/api/users', { params });
  },
  
  getById: async (id: number) => {
    return get(`/api/users/${id}`);
  },
  
  create: async (data: unknown) => {
    return post('/api/users', data);
  },
  
  update: async (id: number, data: unknown) => {
    return put(`/api/users/${id}`, data);
  },
  
  delete: async (id: number) => {
    return del(`/api/users/${id}`);
  },
  
  changePassword: async (id: number, oldPassword: string, newPassword: string) => {
    return post(`/api/users/${id}/change-password`, {
      old_password: oldPassword,
      new_password: newPassword,
    });
  },
};

// ==================== 统计服务 ====================

export const statsService = {
  getDashboard: async () => {
    return get('/api/analytics/dashboard');
  },
  
  getDocumentStats: async (period?: string) => {
    return get('/api/analytics/documents', { params: { period } });
  },
  
  getUserActivity: async (params?: { user_id?: number; limit?: number }) => {
    return get('/api/analytics/activity', { params });
  },
  
  exportReport: async (type: string, format: string) => {
    return get(`/api/analytics/export/${type}`, {
      params: { format },
      responseType: 'blob',
    });
  },
};

export default apiClient;
