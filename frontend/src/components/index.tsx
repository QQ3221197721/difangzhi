/**
 * 地方志系统 - 通用组件库
 */
import React, { useState, useCallback } from 'react';
import {
  Tag,
  Input,
  Select,
  Space,
  Button,
  Modal,
  Card,
  Spin,
  Result,
  DatePicker,
  Row,
  Col,
  Tooltip,
  Badge,
} from 'antd';
import {
  SearchOutlined,
  ClearOutlined,
  ExclamationCircleOutlined,
  LoadingOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import type { DataStatus } from '../types';

const { Option } = Select;
const { RangePicker } = DatePicker;
const { confirm } = Modal;

// ============ 状态标签组件 ============

interface StatusTagProps {
  status: DataStatus;
}

const statusConfig: Record<DataStatus, { color: string; text: string }> = {
  pending: { color: 'orange', text: '待审核' },
  approved: { color: 'green', text: '已通过' },
  rejected: { color: 'red', text: '已拒绝' },
  archived: { color: 'default', text: '已归档' },
};

export const StatusTag: React.FC<StatusTagProps> = ({ status }) => {
  const config = statusConfig[status] || { color: 'default', text: status };
  return <Tag color={config.color}>{config.text}</Tag>;
};

// ============ 角色标签组件 ============

interface RoleTagProps {
  role: string;
}

const roleConfig: Record<string, { color: string; text: string }> = {
  admin: { color: 'red', text: '管理员' },
  editor: { color: 'blue', text: '编辑员' },
  viewer: { color: 'green', text: '访客' },
  uploader: { color: 'orange', text: '上传员' },
};

export const RoleTag: React.FC<RoleTagProps> = ({ role }) => {
  const config = roleConfig[role] || { color: 'default', text: role };
  return <Tag color={config.color}>{config.text}</Tag>;
};

// ============ 分类类型标签 ============

interface CategoryTypeTagProps {
  type: string;
}

const categoryTypeConfig: Record<string, { color: string; text: string }> = {
  region: { color: 'blue', text: '地区' },
  year: { color: 'green', text: '年份' },
  person: { color: 'orange', text: '人物' },
  event: { color: 'purple', text: '事件' },
};

export const CategoryTypeTag: React.FC<CategoryTypeTagProps> = ({ type }) => {
  const config = categoryTypeConfig[type] || { color: 'default', text: type };
  return <Tag color={config.color}>{config.text}</Tag>;
};

// ============ 搜索筛选器组件 ============

export interface FilterValues {
  keyword?: string;
  status?: DataStatus;
  region?: string;
  year_start?: number;
  year_end?: number;
  category_type?: string;
  date_range?: [any, any];
}

interface SearchFilterProps {
  onSearch: (values: FilterValues) => void;
  onReset?: () => void;
  showStatus?: boolean;
  showRegion?: boolean;
  showYear?: boolean;
  showCategoryType?: boolean;
  showDateRange?: boolean;
  loading?: boolean;
  regions?: string[];
}

export const SearchFilter: React.FC<SearchFilterProps> = ({
  onSearch,
  onReset,
  showStatus = true,
  showRegion = false,
  showYear = false,
  showCategoryType = false,
  showDateRange = false,
  loading = false,
  regions = [],
}) => {
  const [filters, setFilters] = useState<FilterValues>({});

  const handleSearch = useCallback(() => {
    onSearch(filters);
  }, [filters, onSearch]);

  const handleReset = useCallback(() => {
    setFilters({});
    onReset?.();
  }, [onReset]);

  const updateFilter = (key: keyof FilterValues, value: any) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <Card size="small" style={{ marginBottom: 16 }}>
      <Row gutter={[16, 16]} align="middle">
        <Col flex="auto">
          <Space wrap size="middle">
            <Input
              placeholder="搜索关键词"
              prefix={<SearchOutlined />}
              style={{ width: 220 }}
              value={filters.keyword || ''}
              onChange={(e) => updateFilter('keyword', e.target.value)}
              onPressEnter={handleSearch}
              allowClear
            />

            {showStatus && (
              <Select
                placeholder="状态筛选"
                style={{ width: 120 }}
                value={filters.status}
                onChange={(v) => updateFilter('status', v)}
                allowClear
              >
                <Option value="pending">待审核</Option>
                <Option value="approved">已通过</Option>
                <Option value="rejected">已拒绝</Option>
                <Option value="archived">已归档</Option>
              </Select>
            )}

            {showRegion && regions.length > 0 && (
              <Select
                placeholder="选择地区"
                style={{ width: 150 }}
                value={filters.region}
                onChange={(v) => updateFilter('region', v)}
                allowClear
                showSearch
              >
                {regions.map((r) => (
                  <Option key={r} value={r}>
                    {r}
                  </Option>
                ))}
              </Select>
            )}

            {showYear && (
              <Space>
                <Select
                  placeholder="起始年份"
                  style={{ width: 100 }}
                  value={filters.year_start}
                  onChange={(v) => updateFilter('year_start', v)}
                  allowClear
                >
                  {Array.from({ length: 51 }, (_, i) => 2000 + i).map((y) => (
                    <Option key={y} value={y}>
                      {y}
                    </Option>
                  ))}
                </Select>
                <span>-</span>
                <Select
                  placeholder="结束年份"
                  style={{ width: 100 }}
                  value={filters.year_end}
                  onChange={(v) => updateFilter('year_end', v)}
                  allowClear
                >
                  {Array.from({ length: 51 }, (_, i) => 2000 + i).map((y) => (
                    <Option key={y} value={y}>
                      {y}
                    </Option>
                  ))}
                </Select>
              </Space>
            )}

            {showCategoryType && (
              <Select
                placeholder="分类类型"
                style={{ width: 120 }}
                value={filters.category_type}
                onChange={(v) => updateFilter('category_type', v)}
                allowClear
              >
                <Option value="region">地区</Option>
                <Option value="year">年份</Option>
                <Option value="person">人物</Option>
                <Option value="event">事件</Option>
              </Select>
            )}

            {showDateRange && (
              <RangePicker
                value={filters.date_range}
                onChange={(dates) => updateFilter('date_range', dates)}
                placeholder={['开始日期', '结束日期']}
              />
            )}
          </Space>
        </Col>

        <Col>
          <Space>
            <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch} loading={loading}>
              搜索
            </Button>
            <Button icon={<ClearOutlined />} onClick={handleReset}>
              重置
            </Button>
          </Space>
        </Col>
      </Row>
    </Card>
  );
};

// ============ 确认对话框 ============

interface ConfirmModalOptions {
  title: string;
  content?: string;
  okText?: string;
  cancelText?: string;
  okType?: 'primary' | 'danger' | 'default';
  onOk: () => void | Promise<void>;
  onCancel?: () => void;
}

export const showConfirmModal = ({
  title,
  content,
  okText = '确定',
  cancelText = '取消',
  okType = 'primary',
  onOk,
  onCancel,
}: ConfirmModalOptions) => {
  confirm({
    title,
    content,
    icon: <ExclamationCircleOutlined />,
    okText,
    cancelText,
    okType: okType === 'danger' ? 'primary' : okType,
    okButtonProps: okType === 'danger' ? { danger: true } : {},
    onOk,
    onCancel,
  });
};

// ============ 删除确认对话框 ============

interface DeleteConfirmOptions {
  itemName?: string;
  onConfirm: () => void | Promise<void>;
}

export const showDeleteConfirm = ({ itemName = '此项', onConfirm }: DeleteConfirmOptions) => {
  showConfirmModal({
    title: '确认删除',
    content: `确定要删除${itemName}吗？此操作不可恢复。`,
    okText: '删除',
    okType: 'danger',
    onOk: onConfirm,
  });
};

// ============ 加载中组件 ============

interface LoadingSpinProps {
  tip?: string;
  size?: 'small' | 'default' | 'large';
  fullScreen?: boolean;
}

export const LoadingSpin: React.FC<LoadingSpinProps> = ({
  tip = '加载中...',
  size = 'large',
  fullScreen = false,
}) => {
  const style: React.CSSProperties = fullScreen
    ? {
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: 'rgba(255, 255, 255, 0.8)',
        zIndex: 9999,
      }
    : {
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        padding: 40,
      };

  return (
    <div style={style}>
      <Spin indicator={<LoadingOutlined style={{ fontSize: size === 'large' ? 32 : 24 }} spin />} tip={tip} />
    </div>
  );
};

// ============ 空状态组件 ============

interface EmptyStateProps {
  title?: string;
  subTitle?: string;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = '暂无数据',
  subTitle,
  action,
}) => (
  <Result
    status="info"
    title={title}
    subTitle={subTitle}
    extra={action}
  />
);

// ============ 错误状态组件 ============

interface ErrorStateProps {
  title?: string;
  subTitle?: string;
  onRetry?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = '加载失败',
  subTitle = '请检查网络连接后重试',
  onRetry,
}) => (
  <Result
    status="error"
    title={title}
    subTitle={subTitle}
    extra={
      onRetry && (
        <Button type="primary" icon={<ReloadOutlined />} onClick={onRetry}>
          重试
        </Button>
      )
    }
  />
);

// ============ 页面头部组件 ============

interface PageHeaderProps {
  title: string;
  subTitle?: string;
  extra?: React.ReactNode;
}

export const PageHeader: React.FC<PageHeaderProps> = ({ title, subTitle, extra }) => (
  <div
    style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: 24,
    }}
  >
    <div>
      <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>{title}</h2>
      {subTitle && <span style={{ color: '#999', fontSize: 14 }}>{subTitle}</span>}
    </div>
    {extra && <div>{extra}</div>}
  </div>
);

// ============ 文件大小显示 ============

interface FileSizeProps {
  bytes: number;
}

export const FileSize: React.FC<FileSizeProps> = ({ bytes }) => {
  const formatSize = (b: number): string => {
    if (b === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(b) / Math.log(k));
    return parseFloat((b / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return <span>{formatSize(bytes)}</span>;
};

// ============ 在线状态指示器 ============

interface OnlineStatusProps {
  online: boolean;
  showText?: boolean;
}

export const OnlineStatus: React.FC<OnlineStatusProps> = ({ online, showText = true }) => (
  <Space size={4}>
    <Badge status={online ? 'success' : 'default'} />
    {showText && <span style={{ color: online ? '#52c41a' : '#999' }}>{online ? '在线' : '离线'}</span>}
  </Space>
);

// ============ 截断文本 ============

interface TruncateTextProps {
  text: string;
  maxLength?: number;
}

export const TruncateText: React.FC<TruncateTextProps> = ({ text, maxLength = 50 }) => {
  if (!text || text.length <= maxLength) {
    return <span>{text || '-'}</span>;
  }

  return (
    <Tooltip title={text}>
      <span>{text.substring(0, maxLength)}...</span>
    </Tooltip>
  );
};

// 导出所有组件
export default {
  StatusTag,
  RoleTag,
  CategoryTypeTag,
  SearchFilter,
  showConfirmModal,
  showDeleteConfirm,
  LoadingSpin,
  EmptyState,
  ErrorState,
  PageHeader,
  FileSize,
  OnlineStatus,
  TruncateText,
};
