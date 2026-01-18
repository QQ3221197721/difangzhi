import React, { Component, ReactNode } from 'react';
import { Spin, Result, Button } from 'antd';
import { LoadingOutlined, ReloadOutlined } from '@ant-design/icons';

// 加载中组件
interface LoadingProps {
  tip?: string;
}

export const Loading: React.FC<LoadingProps> = ({ tip = '加载中...' }) => (
  <div
    style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      height: '100%',
      minHeight: 200,
    }}
  >
    <Spin indicator={<LoadingOutlined style={{ fontSize: 32 }} spin />} tip={tip} />
  </div>
);

// 错误边界组件
interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <Result
          status="error"
          title="页面出错了"
          subTitle="抱歉，页面遇到了一些问题"
          extra={[
            <Button
              type="primary"
              key="reload"
              icon={<ReloadOutlined />}
              onClick={() => window.location.reload()}
            >
              刷新页面
            </Button>,
          ]}
        />
      );
    }
    return this.props.children;
  }
}

// 空状态组件
interface EmptyStateProps {
  description?: string;
  action?: ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ description = '暂无数据', action = null }) => (
  <Result status="info" title={description} extra={action} />
);

// 权限不足组件
export const NoPermission: React.FC = () => (
  <Result
    status="403"
    title="无权限访问"
    subTitle="抱歉，您没有访问此页面的权限"
    extra={
      <Button type="primary" href="/dashboard">
        返回首页
      </Button>
    }
  />
);

// 页面未找到组件
export const NotFound: React.FC = () => (
  <Result
    status="404"
    title="页面未找到"
    subTitle="抱歉，您访问的页面不存在"
    extra={
      <Button type="primary" href="/dashboard">
        返回首页
      </Button>
    }
  />
);

export default { Loading, ErrorBoundary, EmptyState, NoPermission, NotFound };
