// 地方志数据智能管理系统 - 文档状态管理
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import api from '../services/api';

interface Document {
  id: number;
  title: string;
  content: string;
  region?: string;
  year?: number;
  tags?: string[];
  status: string;
  created_at: string;
  updated_at: string;
}

interface DocumentFilters {
  q?: string;
  region?: string;
  year_start?: number;
  year_end?: number;
  tags?: string[];
  status?: string;
}

interface DocumentState {
  // 状态
  documents: Document[];
  currentDocument: Document | null;
  total: number;
  page: number;
  pageSize: number;
  filters: DocumentFilters;
  loading: boolean;
  error: string | null;
  
  // 操作
  fetchDocuments: () => Promise<void>;
  fetchDocument: (id: number) => Promise<void>;
  createDocument: (data: Partial<Document>) => Promise<Document>;
  updateDocument: (id: number, data: Partial<Document>) => Promise<void>;
  deleteDocument: (id: number) => Promise<void>;
  setPage: (page: number) => void;
  setPageSize: (pageSize: number) => void;
  setFilters: (filters: DocumentFilters) => void;
  clearFilters: () => void;
  setCurrentDocument: (doc: Document | null) => void;
}

export const useDocumentStore = create<DocumentState>()(
  devtools(
    (set, get) => ({
      // 初始状态
      documents: [],
      currentDocument: null,
      total: 0,
      page: 1,
      pageSize: 20,
      filters: {},
      loading: false,
      error: null,

      // 获取文档列表
      fetchDocuments: async () => {
        const { page, pageSize, filters } = get();
        set({ loading: true, error: null });

        try {
          const response = await api.get('/documents', {
            params: { page, page_size: pageSize, ...filters },
          });
          set({
            documents: response.data.data || [],
            total: response.data.page_info?.total || 0,
            loading: false,
          });
        } catch (error: any) {
          set({
            error: error.message || '获取文档列表失败',
            loading: false,
          });
        }
      },

      // 获取单个文档
      fetchDocument: async (id: number) => {
        set({ loading: true, error: null });

        try {
          const response = await api.get(`/documents/${id}`);
          set({
            currentDocument: response.data.data,
            loading: false,
          });
        } catch (error: any) {
          set({
            error: error.message || '获取文档详情失败',
            loading: false,
          });
        }
      },

      // 创建文档
      createDocument: async (data: Partial<Document>) => {
        set({ loading: true, error: null });

        try {
          const response = await api.post('/documents', data);
          const newDoc = response.data.data;
          
          set((state) => ({
            documents: [newDoc, ...state.documents],
            total: state.total + 1,
            loading: false,
          }));
          
          return newDoc;
        } catch (error: any) {
          set({
            error: error.message || '创建文档失败',
            loading: false,
          });
          throw error;
        }
      },

      // 更新文档
      updateDocument: async (id: number, data: Partial<Document>) => {
        set({ loading: true, error: null });

        try {
          const response = await api.put(`/documents/${id}`, data);
          const updatedDoc = response.data.data;
          
          set((state) => ({
            documents: state.documents.map((doc) =>
              doc.id === id ? updatedDoc : doc
            ),
            currentDocument:
              state.currentDocument?.id === id
                ? updatedDoc
                : state.currentDocument,
            loading: false,
          }));
        } catch (error: any) {
          set({
            error: error.message || '更新文档失败',
            loading: false,
          });
          throw error;
        }
      },

      // 删除文档
      deleteDocument: async (id: number) => {
        set({ loading: true, error: null });

        try {
          await api.delete(`/documents/${id}`);
          
          set((state) => ({
            documents: state.documents.filter((doc) => doc.id !== id),
            total: state.total - 1,
            currentDocument:
              state.currentDocument?.id === id ? null : state.currentDocument,
            loading: false,
          }));
        } catch (error: any) {
          set({
            error: error.message || '删除文档失败',
            loading: false,
          });
          throw error;
        }
      },

      // 设置页码
      setPage: (page: number) => {
        set({ page });
        get().fetchDocuments();
      },

      // 设置每页数量
      setPageSize: (pageSize: number) => {
        set({ pageSize, page: 1 });
        get().fetchDocuments();
      },

      // 设置筛选条件
      setFilters: (filters: DocumentFilters) => {
        set({ filters, page: 1 });
        get().fetchDocuments();
      },

      // 清空筛选
      clearFilters: () => {
        set({ filters: {}, page: 1 });
        get().fetchDocuments();
      },

      // 设置当前文档
      setCurrentDocument: (doc: Document | null) => {
        set({ currentDocument: doc });
      },
    }),
    { name: 'document-store' }
  )
);
