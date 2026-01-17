import axios from 'axios';
import { message } from 'antd';

// 创建axios实例
const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
api.interceptors.request.use(
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
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      const refreshToken = localStorage.getItem('refreshToken');
      if (refreshToken) {
        try {
          const response = await axios.post(
            `${api.defaults.baseURL}/auth/refresh`,
            { refresh_token: refreshToken }
          );
          const { access_token, refresh_token } = response.data;
          localStorage.setItem('token', access_token);
          localStorage.setItem('refreshToken', refresh_token);
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        } catch (refreshError) {
          localStorage.removeItem('token');
          localStorage.removeItem('refreshToken');
          window.location.href = '/login';
          return Promise.reject(refreshError);
        }
      }
    }
    
    const errorMessage = error.response?.data?.message || error.message || '请求失败';
    message.error(errorMessage);
    return Promise.reject(error);
  }
);

// 认证服务
export const authService = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  logout: () => api.post('/auth/logout'),
  verifyIdentity: (data) => api.post('/auth/verify-identity', data),
  getCurrentUser: () => api.get('/auth/me'),
  refreshToken: (refreshToken) => api.post('/auth/refresh', { refresh_token: refreshToken }),
  recordLocation: (data) => api.post('/auth/record-location', data),
};

// 文件上传服务
export const uploadService = {
  uploadFile: (file, onProgress) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/upload/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (onProgress) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percent);
        }
      },
    });
  },
  uploadSpreadsheet: (file, onProgress) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/upload/spreadsheet', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (onProgress) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percent);
        }
      },
    });
  },
  uploadManualData: (data) => api.post('/upload/manual', data),
  uploadBatchData: (data) => api.post('/upload/batch', data),
  getFileStatus: (fileId) => api.get(`/upload/status/${fileId}`),
  getUploadHistory: (page = 1, pageSize = 20) => 
    api.get('/upload/history', { params: { page, page_size: pageSize } }),
};

// 搜索服务
export const searchService = {
  aiSearch: (query, limit = 50) => api.post('/search/ai', { query, limit }),
  filterSearch: (filters, page = 1, pageSize = 20, sortBy = null, sortOrder = 'desc') => 
    api.post('/search/filter', { 
      filters, 
      page, 
      page_size: pageSize,
      sort_by: sortBy,
      sort_order: sortOrder 
    }),
  getCategories: () => api.get('/search/categories'),
  getRecordDetail: (recordId) => api.get(`/search/record/${recordId}`),
  getSuggestions: (query) => api.get('/search/suggestions', { params: { query } }),
  getSearchHistory: (limit = 20) => api.get('/search/history', { params: { limit } }),
};

// 数据分析服务
export const analysisService = {
  getSummary: (recordIds, options = {}) => 
    api.post('/analysis/summary', { record_ids: recordIds, analysis_type: 'summary', ...options }),
  getTrend: (recordIds, groupBy = null, metrics = null) => 
    api.post('/analysis/trend', { 
      record_ids: recordIds, 
      analysis_type: 'trend',
      group_by: groupBy,
      metrics 
    }),
  getComparison: (recordIds, groupBy, metrics = null) => 
    api.post('/analysis/comparison', { 
      record_ids: recordIds, 
      analysis_type: 'comparison',
      group_by: groupBy,
      metrics 
    }),
  getDistribution: (recordIds, metrics) => 
    api.post('/analysis/distribution', { 
      record_ids: recordIds, 
      analysis_type: 'distribution',
      metrics 
    }),
  getCorrelation: (recordIds) => 
    api.post('/analysis/correlation', { 
      record_ids: recordIds, 
      analysis_type: 'correlation' 
    }),
  createVisualization: (recordIds, chartType, xField, yField, groupField = null, title = null) =>
    api.post('/analysis/visualize', {
      record_ids: recordIds,
      chart_type: chartType,
      x_field: xField,
      y_field: yField,
      group_field: groupField,
      title,
    }),
  exportExcel: (recordIds) => 
    api.post('/analysis/export/excel', recordIds, { responseType: 'blob' }),
  exportCSV: (recordIds) => 
    api.post('/analysis/export/csv', recordIds, { responseType: 'blob' }),
  getChartTypes: () => api.get('/analysis/chart-types'),
};

// AI助手服务
export const aiService = {
  chat: (message, sessionId = null, contextRecordIds = null) => 
    api.post('/ai/chat', { 
      message, 
      session_id: sessionId,
      context_record_ids: contextRecordIds 
    }),
  getSessions: () => api.get('/ai/sessions'),
  getSessionHistory: (sessionId) => api.get(`/ai/session/${sessionId}`),
  deleteSession: (sessionId) => api.delete(`/ai/session/${sessionId}`),
  analyzeQuery: (query) => api.post('/ai/analyze-query', null, { params: { query } }),
  generateReport: (recordIds, reportType = 'summary') => 
    api.post('/ai/generate-report', null, { 
      params: { report_type: reportType },
      data: recordIds 
    }),
};

export default api;
