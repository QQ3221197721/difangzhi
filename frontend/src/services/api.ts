import axios from 'axios';
import { message } from 'antd';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth-storage');
    if (token) {
      try {
        const parsed = JSON.parse(token);
        if (parsed.state?.accessToken) {
          config.headers.Authorization = `Bearer ${parsed.state.accessToken}`;
        }
      } catch (e) {
        console.error('Token parse error:', e);
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response) {
      const { status, data } = error.response;
      
      switch (status) {
        case 401:
          message.error('登录已过期，请重新登录');
          localStorage.removeItem('auth-storage');
          window.location.href = '/login';
          break;
        case 403:
          message.error('没有权限执行此操作');
          break;
        case 404:
          message.error('请求的资源不存在');
          break;
        case 422:
          message.error(data.message || '请求参数错误');
          break;
        case 500:
          message.error('服务器内部错误');
          break;
        default:
          message.error(data.message || '请求失败');
      }
    } else if (error.request) {
      message.error('网络连接失败，请检查网络');
    } else {
      message.error('请求配置错误');
    }
    
    return Promise.reject(error);
  }
);

export default api;

// 文档相关 API
export const documentApi = {
  list: (params: any) => api.get('/documents', { params }),
  get: (id: number) => api.get(`/documents/${id}`),
  create: (data: any) => api.post('/documents/manual', data),
  update: (id: number, data: any) => api.put(`/documents/${id}`, data),
  delete: (id: number) => api.delete(`/documents/${id}`),
  upload: (formData: FormData) => api.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  review: (id: number, data: any) => api.post(`/documents/${id}/review`, data),
};

// 分类相关 API
export const categoryApi = {
  list: (params?: any) => api.get('/categories', { params }),
  tree: (params?: any) => api.get('/categories/tree', { params }),
  get: (id: number) => api.get(`/categories/${id}`),
  create: (data: any) => api.post('/categories', data),
  update: (id: number, data: any) => api.put(`/categories/${id}`, data),
  delete: (id: number) => api.delete(`/categories/${id}`),
};

// AI 相关 API
export const aiApi = {
  search: (data: any) => api.post('/ai/search', data),
  chat: (data: any) => api.post('/ai/chat', data),
  getChatHistory: (sessionId: string) => api.get(`/ai/chat/${sessionId}`),
  getChatSessions: () => api.get('/ai/chat/history'),
  summarize: (documentId: number) => api.post(`/ai/summarize/${documentId}`),
};

// 数据分析 API
export const analyticsApi = {
  overview: () => api.get('/analytics/overview'),
  byRegion: () => api.get('/analytics/documents/by-region'),
  byYear: (params?: any) => api.get('/analytics/documents/by-year', { params }),
  byCategory: (params?: any) => api.get('/analytics/documents/by-category', { params }),
  uploadTrend: (params?: any) => api.get('/analytics/documents/upload-trend', { params }),
};

// 用户相关 API
export const userApi = {
  list: (params?: any) => api.get('/users', { params }),
  get: (id: number) => api.get(`/users/${id}`),
  update: (id: number, data: any) => api.put(`/users/${id}`, data),
  updateRole: (id: number, role: string) => api.put(`/users/${id}/role`, null, { params: { role } }),
  updateStatus: (id: number, isActive: boolean) => api.put(`/users/${id}/status`, null, { params: { is_active: isActive } }),
};

// 认证相关 API
export const authApi = {
  login: (data: { username: string; password: string; location?: { latitude: number; longitude: number } }) =>
    api.post('/auth/login', data),
  register: (data: { username: string; password: string; real_name: string; email?: string; phone?: string }) =>
    api.post('/auth/register', data),
  logout: () => api.post('/auth/logout'),
  refreshToken: (refreshToken: string) => api.post('/auth/refresh', { refresh_token: refreshToken }),
  changePassword: (data: { old_password: string; new_password: string }) =>
    api.post('/auth/change-password', data),
  resetPassword: (data: { email: string }) => api.post('/auth/reset-password', data),
  verifyEmail: (token: string) => api.post('/auth/verify-email', { token }),
  me: () => api.get('/auth/me'),
  getLoginLogs: () => api.get('/auth/login-logs'),
  uploadAvatar: (formData: FormData) => api.post('/users/avatar', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
};
