// 地方志数据智能管理系统 - 应用状态管理
import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

interface AppState {
  // UI状态
  sidebarCollapsed: boolean;
  theme: 'light' | 'dark';
  locale: 'zh-CN' | 'en-US';
  
  // 全局加载状态
  globalLoading: boolean;
  loadingText: string;
  
  // 操作
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setTheme: (theme: 'light' | 'dark') => void;
  setLocale: (locale: 'zh-CN' | 'en-US') => void;
  setGlobalLoading: (loading: boolean, text?: string) => void;
}

export const useAppStore = create<AppState>()(
  devtools(
    persist(
      (set) => ({
        // 初始状态
        sidebarCollapsed: false,
        theme: 'light',
        locale: 'zh-CN',
        globalLoading: false,
        loadingText: '',

        // 切换侧边栏
        toggleSidebar: () => {
          set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed }));
        },

        // 设置侧边栏状态
        setSidebarCollapsed: (collapsed: boolean) => {
          set({ sidebarCollapsed: collapsed });
        },

        // 设置主题
        setTheme: (theme: 'light' | 'dark') => {
          set({ theme });
          document.documentElement.setAttribute('data-theme', theme);
        },

        // 设置语言
        setLocale: (locale: 'zh-CN' | 'en-US') => {
          set({ locale });
        },

        // 设置全局加载状态
        setGlobalLoading: (loading: boolean, text?: string) => {
          set({ globalLoading: loading, loadingText: text || '' });
        },
      }),
      {
        name: 'app-storage',
        partialize: (state) => ({
          sidebarCollapsed: state.sidebarCollapsed,
          theme: state.theme,
          locale: state.locale,
        }),
      }
    ),
    { name: 'app-store' }
  )
);
