// 地方志数据智能管理系统 - 分类状态管理
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import api from '../services/api';

interface Category {
  id: number;
  name: string;
  code: string;
  level: number;
  parent_id?: number;
  category_type: string;
  description?: string;
  sort_order: number;
  is_active: boolean;
  children?: Category[];
}

interface CategoryState {
  // 状态
  categories: Category[];
  categoryTree: Category[];
  loading: boolean;
  error: string | null;
  
  // 操作
  fetchCategories: (type?: string) => Promise<void>;
  createCategory: (data: Partial<Category>) => Promise<Category>;
  updateCategory: (id: number, data: Partial<Category>) => Promise<void>;
  deleteCategory: (id: number) => Promise<void>;
  getCategoryById: (id: number) => Category | undefined;
  getCategoriesByType: (type: string) => Category[];
}

// 构建分类树
function buildCategoryTree(categories: Category[]): Category[] {
  const map = new Map<number, Category>();
  const roots: Category[] = [];

  // 先创建所有节点
  categories.forEach((cat) => {
    map.set(cat.id, { ...cat, children: [] });
  });

  // 构建树结构
  categories.forEach((cat) => {
    const node = map.get(cat.id)!;
    if (cat.parent_id && map.has(cat.parent_id)) {
      const parent = map.get(cat.parent_id)!;
      parent.children = parent.children || [];
      parent.children.push(node);
    } else {
      roots.push(node);
    }
  });

  // 排序
  const sortChildren = (nodes: Category[]) => {
    nodes.sort((a, b) => a.sort_order - b.sort_order);
    nodes.forEach((node) => {
      if (node.children?.length) {
        sortChildren(node.children);
      }
    });
  };
  sortChildren(roots);

  return roots;
}

export const useCategoryStore = create<CategoryState>()(
  devtools(
    (set, get) => ({
      // 初始状态
      categories: [],
      categoryTree: [],
      loading: false,
      error: null,

      // 获取分类列表
      fetchCategories: async (type?: string) => {
        set({ loading: true, error: null });

        try {
          const params = type ? { type } : {};
          const response = await api.get('/categories', { params });
          const categories = response.data.data || [];
          
          set({
            categories,
            categoryTree: buildCategoryTree(categories),
            loading: false,
          });
        } catch (error: any) {
          set({
            error: error.message || '获取分类失败',
            loading: false,
          });
        }
      },

      // 创建分类
      createCategory: async (data: Partial<Category>) => {
        set({ loading: true, error: null });

        try {
          const response = await api.post('/categories', data);
          const newCategory = response.data.data;
          
          set((state) => {
            const categories = [...state.categories, newCategory];
            return {
              categories,
              categoryTree: buildCategoryTree(categories),
              loading: false,
            };
          });
          
          return newCategory;
        } catch (error: any) {
          set({
            error: error.message || '创建分类失败',
            loading: false,
          });
          throw error;
        }
      },

      // 更新分类
      updateCategory: async (id: number, data: Partial<Category>) => {
        set({ loading: true, error: null });

        try {
          const response = await api.put(`/categories/${id}`, data);
          const updatedCategory = response.data.data;
          
          set((state) => {
            const categories = state.categories.map((cat) =>
              cat.id === id ? updatedCategory : cat
            );
            return {
              categories,
              categoryTree: buildCategoryTree(categories),
              loading: false,
            };
          });
        } catch (error: any) {
          set({
            error: error.message || '更新分类失败',
            loading: false,
          });
          throw error;
        }
      },

      // 删除分类
      deleteCategory: async (id: number) => {
        set({ loading: true, error: null });

        try {
          await api.delete(`/categories/${id}`);
          
          set((state) => {
            const categories = state.categories.filter((cat) => cat.id !== id);
            return {
              categories,
              categoryTree: buildCategoryTree(categories),
              loading: false,
            };
          });
        } catch (error: any) {
          set({
            error: error.message || '删除分类失败',
            loading: false,
          });
          throw error;
        }
      },

      // 根据ID获取分类
      getCategoryById: (id: number) => {
        return get().categories.find((cat) => cat.id === id);
      },

      // 根据类型获取分类
      getCategoriesByType: (type: string) => {
        return get().categories.filter((cat) => cat.category_type === type);
      },
    }),
    { name: 'category-store' }
  )
);
