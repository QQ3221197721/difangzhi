/**
 * 前端性能优化工具集
 * Frontend Performance Optimization Utilities
 * 
 * 包含:
 * - 虚拟滚动
 * - 懒加载
 * - 性能监控
 * - 资源预加载
 * - 防抖节流
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

// ==================== 虚拟滚动 ====================

interface VirtualScrollOptions {
  itemHeight: number;
  overscan?: number;
  containerHeight: number;
}

interface VirtualScrollResult<T> {
  virtualItems: { index: number; item: T; style: React.CSSProperties }[];
  totalHeight: number;
  containerStyle: React.CSSProperties;
  onScroll: (e: React.UIEvent<HTMLElement>) => void;
}

export function useVirtualScroll<T>(
  items: T[],
  options: VirtualScrollOptions
): VirtualScrollResult<T> {
  const { itemHeight, overscan = 3, containerHeight } = options;
  const [scrollTop, setScrollTop] = useState(0);

  const totalHeight = items.length * itemHeight;
  
  const virtualItems = useMemo(() => {
    const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
    const endIndex = Math.min(
      items.length,
      Math.ceil((scrollTop + containerHeight) / itemHeight) + overscan
    );

    return items.slice(startIndex, endIndex).map((item, i) => ({
      index: startIndex + i,
      item,
      style: {
        position: 'absolute' as const,
        top: (startIndex + i) * itemHeight,
        height: itemHeight,
        left: 0,
        right: 0,
      },
    }));
  }, [items, scrollTop, itemHeight, containerHeight, overscan]);

  const onScroll = useCallback((e: React.UIEvent<HTMLElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  }, []);

  const containerStyle: React.CSSProperties = {
    position: 'relative',
    height: totalHeight,
    overflow: 'hidden',
  };

  return { virtualItems, totalHeight, containerStyle, onScroll };
}

// ==================== 懒加载 ====================

interface LazyLoadOptions {
  threshold?: number;
  rootMargin?: string;
  triggerOnce?: boolean;
}

export function useLazyLoad(options: LazyLoadOptions = {}) {
  const { threshold = 0.1, rootMargin = '100px', triggerOnce = true } = options;
  const [isVisible, setIsVisible] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false);
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element || (triggerOnce && hasLoaded)) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          setHasLoaded(true);
          if (triggerOnce) {
            observer.unobserve(element);
          }
        } else if (!triggerOnce) {
          setIsVisible(false);
        }
      },
      { threshold, rootMargin }
    );

    observer.observe(element);
    return () => observer.unobserve(element);
  }, [threshold, rootMargin, triggerOnce, hasLoaded]);

  return { ref, isVisible, hasLoaded };
}

// 图片懒加载组件
interface LazyImageProps extends React.ImgHTMLAttributes<HTMLImageElement> {
  placeholder?: string;
  onLoad?: () => void;
  onError?: () => void;
}

export function LazyImage({
  src,
  placeholder = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"%3E%3C/svg%3E',
  onLoad,
  onError,
  ...props
}: LazyImageProps) {
  const { ref, isVisible } = useLazyLoad({ triggerOnce: true });
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);

  const handleLoad = () => {
    setLoaded(true);
    onLoad?.();
  };

  const handleError = () => {
    setError(true);
    onError?.();
  };

  return (
    <img
      ref={ref as React.RefObject<HTMLImageElement>}
      src={isVisible && !error ? src : placeholder}
      onLoad={handleLoad}
      onError={handleError}
      style={{
        opacity: loaded ? 1 : 0.5,
        transition: 'opacity 0.3s',
        ...props.style,
      }}
      {...props}
    />
  );
}

// ==================== 防抖节流 ====================

export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}

export function useDebouncedCallback<T extends (...args: any[]) => any>(
  callback: T,
  delay: number
): T {
  const callbackRef = useRef(callback);
  const timeoutRef = useRef<NodeJS.Timeout>();

  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  return useCallback(
    ((...args: Parameters<T>) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = setTimeout(() => {
        callbackRef.current(...args);
      }, delay);
    }) as T,
    [delay]
  );
}

export function useThrottle<T>(value: T, interval: number): T {
  const [throttledValue, setThrottledValue] = useState(value);
  const lastUpdated = useRef<number>(Date.now());

  useEffect(() => {
    const now = Date.now();
    if (now - lastUpdated.current >= interval) {
      lastUpdated.current = now;
      setThrottledValue(value);
    } else {
      const timer = setTimeout(() => {
        lastUpdated.current = Date.now();
        setThrottledValue(value);
      }, interval - (now - lastUpdated.current));
      return () => clearTimeout(timer);
    }
  }, [value, interval]);

  return throttledValue;
}

export function useThrottledCallback<T extends (...args: any[]) => any>(
  callback: T,
  interval: number
): T {
  const callbackRef = useRef(callback);
  const lastRan = useRef<number>(0);
  const timeoutRef = useRef<NodeJS.Timeout>();

  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  return useCallback(
    ((...args: Parameters<T>) => {
      const now = Date.now();
      if (now - lastRan.current >= interval) {
        lastRan.current = now;
        callbackRef.current(...args);
      } else {
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        timeoutRef.current = setTimeout(() => {
          lastRan.current = Date.now();
          callbackRef.current(...args);
        }, interval - (now - lastRan.current));
      }
    }) as T,
    [interval]
  );
}

// ==================== 性能监控 ====================

interface PerformanceMetrics {
  fcp: number | null;  // First Contentful Paint
  lcp: number | null;  // Largest Contentful Paint
  fid: number | null;  // First Input Delay
  cls: number | null;  // Cumulative Layout Shift
  ttfb: number | null; // Time to First Byte
}

export function usePerformanceMetrics(): PerformanceMetrics {
  const [metrics, setMetrics] = useState<PerformanceMetrics>({
    fcp: null,
    lcp: null,
    fid: null,
    cls: null,
    ttfb: null,
  });

  useEffect(() => {
    // First Contentful Paint
    const fcpObserver = new PerformanceObserver((list) => {
      const entries = list.getEntries();
      const fcp = entries.find(e => e.name === 'first-contentful-paint');
      if (fcp) {
        setMetrics(m => ({ ...m, fcp: fcp.startTime }));
      }
    });
    fcpObserver.observe({ entryTypes: ['paint'] });

    // Largest Contentful Paint
    const lcpObserver = new PerformanceObserver((list) => {
      const entries = list.getEntries();
      const lcp = entries[entries.length - 1];
      if (lcp) {
        setMetrics(m => ({ ...m, lcp: lcp.startTime }));
      }
    });
    lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] });

    // First Input Delay
    const fidObserver = new PerformanceObserver((list) => {
      const entries = list.getEntries();
      const fid = entries[0] as PerformanceEventTiming;
      if (fid) {
        setMetrics(m => ({ ...m, fid: fid.processingStart - fid.startTime }));
      }
    });
    fidObserver.observe({ entryTypes: ['first-input'] });

    // Cumulative Layout Shift
    let clsValue = 0;
    const clsObserver = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (!(entry as any).hadRecentInput) {
          clsValue += (entry as any).value;
        }
      }
      setMetrics(m => ({ ...m, cls: clsValue }));
    });
    clsObserver.observe({ entryTypes: ['layout-shift'] });

    // Time to First Byte
    const navEntry = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    if (navEntry) {
      setMetrics(m => ({ ...m, ttfb: navEntry.responseStart - navEntry.requestStart }));
    }

    return () => {
      fcpObserver.disconnect();
      lcpObserver.disconnect();
      fidObserver.disconnect();
      clsObserver.disconnect();
    };
  }, []);

  return metrics;
}

// 组件渲染性能追踪
export function useRenderCount(componentName: string): number {
  const renderCount = useRef(0);
  renderCount.current += 1;

  useEffect(() => {
    if (process.env.NODE_ENV === 'development') {
      console.log(`[Render] ${componentName}: ${renderCount.current}`);
    }
  });

  return renderCount.current;
}

// 渲染时间追踪
export function useRenderTime(componentName: string) {
  const startTime = useRef(performance.now());

  useEffect(() => {
    const endTime = performance.now();
    const renderTime = endTime - startTime.current;
    
    if (process.env.NODE_ENV === 'development' && renderTime > 16) {
      console.warn(`[Slow Render] ${componentName}: ${renderTime.toFixed(2)}ms`);
    }
    
    startTime.current = performance.now();
  });
}

// ==================== 资源预加载 ====================

export function preloadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

export function preloadImages(srcs: string[]): Promise<HTMLImageElement[]> {
  return Promise.all(srcs.map(preloadImage));
}

export function prefetchPage(url: string) {
  const link = document.createElement('link');
  link.rel = 'prefetch';
  link.href = url;
  document.head.appendChild(link);
}

export function preconnect(url: string) {
  const link = document.createElement('link');
  link.rel = 'preconnect';
  link.href = url;
  document.head.appendChild(link);
}

// ==================== 缓存 ====================

interface CacheOptions {
  ttl?: number; // 毫秒
  maxSize?: number;
}

class LRUCache<K, V> {
  private cache = new Map<K, { value: V; expiry: number }>();
  private maxSize: number;
  private defaultTTL: number;

  constructor(options: CacheOptions = {}) {
    this.maxSize = options.maxSize || 100;
    this.defaultTTL = options.ttl || 5 * 60 * 1000; // 5分钟
  }

  get(key: K): V | undefined {
    const item = this.cache.get(key);
    if (!item) return undefined;
    
    if (Date.now() > item.expiry) {
      this.cache.delete(key);
      return undefined;
    }
    
    // 移到末尾(最近使用)
    this.cache.delete(key);
    this.cache.set(key, item);
    
    return item.value;
  }

  set(key: K, value: V, ttl?: number): void {
    // 淘汰策略
    if (this.cache.size >= this.maxSize) {
      const firstKey = this.cache.keys().next().value;
      this.cache.delete(firstKey);
    }
    
    this.cache.set(key, {
      value,
      expiry: Date.now() + (ttl || this.defaultTTL),
    });
  }

  delete(key: K): boolean {
    return this.cache.delete(key);
  }

  clear(): void {
    this.cache.clear();
  }

  get size(): number {
    return this.cache.size;
  }
}

// 全局缓存实例
export const requestCache = new LRUCache<string, any>({ maxSize: 200, ttl: 60000 });

// 带缓存的请求Hook
export function useCachedFetch<T>(
  url: string,
  options?: RequestInit & { ttl?: number }
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    // 检查缓存
    const cached = requestCache.get(url);
    if (cached) {
      setData(cached);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(url, options);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      
      const result = await response.json();
      requestCache.set(url, result, options?.ttl);
      setData(result);
    } catch (err) {
      setError(err as Error);
    } finally {
      setLoading(false);
    }
  }, [url, options]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const refresh = useCallback(() => {
    requestCache.delete(url);
    fetchData();
  }, [url, fetchData]);

  return { data, loading, error, refresh };
}

// ==================== 内存优化 ====================

// 清理未使用的引用
export function useCleanup(cleanupFn: () => void) {
  useEffect(() => {
    return () => {
      cleanupFn();
    };
  }, [cleanupFn]);
}

// 分页数据管理(避免大量数据占用内存)
export function usePaginatedData<T>(
  fetchFn: (page: number) => Promise<T[]>,
  pageSize: number = 20
) {
  const [pages, setPages] = useState<Map<number, T[]>>(new Map());
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const maxPagesInMemory = 5;

  const loadPage = useCallback(async (page: number) => {
    if (pages.has(page)) {
      setCurrentPage(page);
      return;
    }

    setLoading(true);
    try {
      const data = await fetchFn(page);
      
      setPages(prev => {
        const next = new Map(prev);
        next.set(page, data);
        
        // 清理过远的页面
        if (next.size > maxPagesInMemory) {
          const sortedKeys = Array.from(next.keys()).sort((a, b) => 
            Math.abs(a - page) - Math.abs(b - page)
          );
          for (let i = maxPagesInMemory; i < sortedKeys.length; i++) {
            next.delete(sortedKeys[i]);
          }
        }
        
        return next;
      });
      
      setCurrentPage(page);
      setHasMore(data.length >= pageSize);
    } finally {
      setLoading(false);
    }
  }, [fetchFn, pages, pageSize]);

  const currentData = pages.get(currentPage) || [];

  return {
    data: currentData,
    currentPage,
    loading,
    hasMore,
    loadPage,
    loadNext: () => loadPage(currentPage + 1),
    loadPrev: () => loadPage(Math.max(1, currentPage - 1)),
  };
}

// ==================== 导出 ====================

export {
  LRUCache,
  type VirtualScrollOptions,
  type VirtualScrollResult,
  type LazyLoadOptions,
  type PerformanceMetrics,
  type CacheOptions,
};
