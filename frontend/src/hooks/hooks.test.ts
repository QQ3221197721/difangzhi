/**
 * 地方志数据智能管理系统 - Hooks测试
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useDebounce, useThrottle, useLocalStorage } from '../hooks';

describe('Hooks', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('useDebounce', () => {
    it('should debounce value changes', async () => {
      const { result, rerender } = renderHook(
        ({ value, delay }) => useDebounce(value, delay),
        { initialProps: { value: 'initial', delay: 500 } }
      );

      expect(result.current).toBe('initial');

      // 更新值
      rerender({ value: 'updated', delay: 500 });
      
      // 立即检查，值应该还是旧的
      expect(result.current).toBe('initial');

      // 等待debounce时间
      act(() => {
        vi.advanceTimersByTime(500);
      });

      expect(result.current).toBe('updated');
    });
  });

  describe('useThrottle', () => {
    it('should throttle value changes', async () => {
      const { result, rerender } = renderHook(
        ({ value, interval }) => useThrottle(value, interval),
        { initialProps: { value: 'initial', interval: 500 } }
      );

      expect(result.current).toBe('initial');

      // 快速连续更新
      rerender({ value: 'update1', interval: 500 });
      rerender({ value: 'update2', interval: 500 });
      rerender({ value: 'update3', interval: 500 });

      // 应该只有第一个值通过
      expect(result.current).toBe('initial');

      act(() => {
        vi.advanceTimersByTime(500);
      });

      // 节流后应该是最新值
      expect(result.current).toBe('update3');
    });
  });

  describe('useLocalStorage', () => {
    const localStorageMock = {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    };

    beforeEach(() => {
      Object.defineProperty(window, 'localStorage', {
        value: localStorageMock,
        writable: true,
      });
      localStorageMock.getItem.mockReset();
      localStorageMock.setItem.mockReset();
    });

    it('should return initial value when localStorage is empty', () => {
      localStorageMock.getItem.mockReturnValue(null);

      const { result } = renderHook(() =>
        useLocalStorage('test-key', 'default')
      );

      expect(result.current[0]).toBe('default');
    });

    it('should return stored value from localStorage', () => {
      localStorageMock.getItem.mockReturnValue(JSON.stringify('stored'));

      const { result } = renderHook(() =>
        useLocalStorage('test-key', 'default')
      );

      expect(result.current[0]).toBe('stored');
    });

    it('should update localStorage when value changes', () => {
      localStorageMock.getItem.mockReturnValue(null);

      const { result } = renderHook(() =>
        useLocalStorage('test-key', 'default')
      );

      act(() => {
        result.current[1]('new value');
      });

      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        'test-key',
        JSON.stringify('new value')
      );
    });
  });
});
