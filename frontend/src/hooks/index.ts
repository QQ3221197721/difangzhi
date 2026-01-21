// 地方志数据智能管理系统 - 前端Hooks
// 自定义React Hooks集合

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { message } from 'antd';
import api from '../services/api';
import { useAuthStore } from '../stores/authStore';

// ============== 通用Hooks ==============

/**
 * 防抖Hook
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}

/**
 * 节流Hook
 */
export function useThrottle<T>(value: T, interval: number): T {
  const [throttledValue, setThrottledValue] = useState<T>(value);
  const lastExecuted = useRef<number>(Date.now());

  useEffect(() => {
    if (Date.now() >= lastExecuted.current + interval) {
      lastExecuted.current = Date.now();
      setThrottledValue(value);
    } else {
      const timer = setTimeout(() => {
        lastExecuted.current = Date.now();
        setThrottledValue(value);
      }, interval);
      return () => clearTimeout(timer);
    }
  }, [value, interval]);

  return throttledValue;
}

/**
 * 本地存储Hook
 */
export function useLocalStorage<T>(key: string, initialValue: T): [T, (value: T) => void] {
  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      return initialValue;
    }
  });

  const setValue = (value: T) => {
    try {
      setStoredValue(value);
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
      console.error('Error saving to localStorage:', error);
    }
  };

  return [storedValue, setValue];
}

/**
 * 分页数据Hook
 */
export function usePagination<T>(
  fetchFn: (params: any) => Promise<{ data: T[]; total: number }>,
  initialParams: Record<string, any> = {}
) {
  const [data, setData] = useState<T[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [params, setParams] = useState({
    page: 1,
    pageSize: 20,
    ...initialParams,
  });

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetchFn(params);
      setData(result.data);
      setTotal(result.total);
    } catch (error) {
      message.error('获取数据失败');
    } finally {
      setLoading(false);
    }
  }, [params, fetchFn]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  const changePage = (page: number, pageSize?: number) => {
    setParams((prev) => ({ ...prev, page, pageSize: pageSize || prev.pageSize }));
  };

  const changeParams = (newParams: Record<string, any>) => {
    setParams((prev) => ({ ...prev, ...newParams, page: 1 }));
  };

  const refresh = () => fetch();

  return { data, loading, total, params, changePage, changeParams, refresh };
}

// ============== 业务Hooks ==============

/**
 * 文档列表Hook
 */
export function useDocuments(initialFilters?: Record<string, any>) {
  return usePagination(
    async (params) => {
      const response = await api.get('/documents', { params });
      return {
        data: response.data.data,
        total: response.data.page_info?.total || 0,
      };
    },
    initialFilters
  );
}

/**
 * 单个文档Hook
 */
export function useDocument(id: number | string | null) {
  const [document, setDocument] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const response = await api.get(`/documents/${id}`);
      setDocument(response.data.data);
    } catch (err: any) {
      setError(err.message || '获取文档失败');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { document, loading, error, refresh: fetch };
}

/**
 * 分类数据Hook
 */
export function useCategories(type?: string) {
  const [categories, setCategories] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetch = async () => {
      setLoading(true);
      try {
        const params = type ? { type } : {};
        const response = await api.get('/categories', { params });
        setCategories(response.data.data || []);
      } catch (error) {
        message.error('获取分类失败');
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [type]);

  // 构建分类树
  const categoryTree = useMemo(() => {
    const map = new Map();
    const roots: any[] = [];

    categories.forEach((cat) => map.set(cat.id, { ...cat, children: [] }));
    categories.forEach((cat) => {
      if (cat.parent_id && map.has(cat.parent_id)) {
        map.get(cat.parent_id).children.push(map.get(cat.id));
      } else {
        roots.push(map.get(cat.id));
      }
    });

    return roots;
  }, [categories]);

  return { categories, categoryTree, loading };
}

/**
 * 统计数据Hook
 */
export function useAnalytics(period: string = 'month') {
  const [overview, setOverview] = useState<any>(null);
  const [trends, setTrends] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetch = async () => {
      setLoading(true);
      try {
        const [overviewRes, trendsRes] = await Promise.all([
          api.get('/analytics/overview'),
          api.get('/analytics/trends', { params: { period } }),
        ]);
        setOverview(overviewRes.data.data);
        setTrends(trendsRes.data.data || []);
      } catch (error) {
        message.error('获取统计数据失败');
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [period]);

  return { overview, trends, loading };
}

/**
 * 搜索Hook
 */
export function useSearch() {
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);

  const search = useCallback(async (params: Record<string, any>) => {
    setLoading(true);
    try {
      const response = await api.get('/documents', { params });
      setResults(response.data.data || []);
      setTotal(response.data.page_info?.total || 0);
    } catch (error) {
      message.error('搜索失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const semanticSearch = useCallback(async (query: string) => {
    setLoading(true);
    try {
      const response = await api.get('/ai/search', { params: { q: query } });
      setResults(response.data.data || []);
      setTotal(response.data.data?.length || 0);
    } catch (error) {
      message.error('语义搜索失败');
    } finally {
      setLoading(false);
    }
  }, []);

  return { results, loading, total, search, semanticSearch };
}

/**
 * 文件上传Hook
 */
export function useUpload() {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  const upload = useCallback(async (file: File, onProgress?: (percent: number) => void) => {
    setUploading(true);
    setProgress(0);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await api.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (event) => {
          const percent = Math.round((event.loaded * 100) / (event.total || 1));
          setProgress(percent);
          onProgress?.(percent);
        },
      });
      message.success('上传成功');
      return response.data.data;
    } catch (error) {
      message.error('上传失败');
      throw error;
    } finally {
      setUploading(false);
    }
  }, []);

  return { upload, uploading, progress };
}

/**
 * AI对话Hook
 */
export function useAIChat() {
  const [messages, setMessages] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const sendMessage = useCallback(async (content: string) => {
    const userMessage = { role: 'user', content, timestamp: new Date() };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      const response = await api.post('/ai/chat', {
        message: content,
        session_id: sessionId,
      });

      const { answer, session_id, sources } = response.data.data;
      setSessionId(session_id);

      const aiMessage = {
        role: 'assistant',
        content: answer,
        sources,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiMessage]);

      return aiMessage;
    } catch (error) {
      message.error('AI回复失败');
      throw error;
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  const clearHistory = useCallback(() => {
    setMessages([]);
    setSessionId(null);
  }, []);

  return { messages, loading, sendMessage, clearHistory, sessionId };
}

/**
 * 用户列表Hook (管理员)
 */
export function useUsers() {
  return usePagination(async (params) => {
    const response = await api.get('/users', { params });
    return {
      data: response.data.data,
      total: response.data.page_info?.total || 0,
    };
  });
}

/**
 * 权限检查Hook
 */
export function usePermission() {
  const { user } = useAuthStore();

  const hasRole = useCallback(
    (roles: string | string[]) => {
      if (!user) return false;
      const roleList = Array.isArray(roles) ? roles : [roles];
      return roleList.includes(user.role);
    },
    [user]
  );

  const isAdmin = useMemo(() => hasRole('admin'), [hasRole]);
  const isEditor = useMemo(() => hasRole(['admin', 'editor']), [hasRole]);

  return { hasRole, isAdmin, isEditor };
}

// 默认导出
export default {
  useDebounce,
  useThrottle,
  useLocalStorage,
  usePagination,
  useDocuments,
  useDocument,
  useCategories,
  useAnalytics,
  useSearch,
  useUpload,
  useAIChat,
  useUsers,
  usePermission,
};
