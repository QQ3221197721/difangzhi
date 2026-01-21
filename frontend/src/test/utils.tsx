/**
 * 地方志数据智能管理系统 - 测试工具函数
 */

import { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { vi } from 'vitest';

// 自定义渲染函数，包含Provider
const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  return (
    <BrowserRouter>
      {children}
    </BrowserRouter>
  );
};

const customRender = (
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) => render(ui, { wrapper: AllTheProviders, ...options });

export * from '@testing-library/react';
export { customRender as render };

// Mock数据生成
export const mockUser = (overrides = {}) => ({
  id: 1,
  username: 'testuser',
  email: 'test@example.com',
  full_name: 'Test User',
  role: 'editor' as const,
  is_active: true,
  created_at: '2024-01-01T00:00:00Z',
  ...overrides,
});

export const mockDocument = (overrides = {}) => ({
  id: 1,
  title: '测试文档',
  content: '这是测试内容',
  region: '北京',
  year: 2024,
  tags: ['测试', '示例'],
  status: 'approved' as const,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  ...overrides,
});

export const mockCategory = (overrides = {}) => ({
  id: 1,
  name: '测试分类',
  code: 'test',
  level: 1,
  category_type: 'region' as const,
  sort_order: 1,
  ...overrides,
});

// API Mock helpers
export const mockApiResponse = <T>(data: T) => ({
  data,
  status: 200,
  statusText: 'OK',
  headers: {},
  config: {},
});

export const mockApiError = (message: string, code = 400) => {
  const error = new Error(message);
  (error as any).response = {
    status: code,
    data: { message, code },
  };
  return error;
};

// 等待异步操作
export const waitForAsync = (ms = 0) =>
  new Promise((resolve) => setTimeout(resolve, ms));

// Mock API服务
export const createMockApiClient = () => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
});

// Mock fetch响应
export const mockFetch = (data: unknown, ok = true) => {
  (global.fetch as any).mockResolvedValueOnce({
    ok,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  });
};
