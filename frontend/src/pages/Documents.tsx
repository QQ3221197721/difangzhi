import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Table, Card, Input, Button, Space, Tag, Typography, Select } from 'antd';
import { SearchOutlined, PlusOutlined, EyeOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { documentApi } from '../services/api';

const { Title } = Typography;

interface Document {
  id: number;
  title: string;
  content?: string;
  source?: string;
  region?: string;
  year?: number;
  status: string;
  view_count: number;
  created_at: string;
}

const statusColors: Record<string, string> = {
  pending: 'orange',
  approved: 'green',
  rejected: 'red',
  archived: 'default',
};

const statusLabels: Record<string, string> = {
  pending: '待审核',
  approved: '已通过',
  rejected: '已拒绝',
  archived: '已归档',
};

const Documents: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [keyword, setKeyword] = useState('');
  const [status, setStatus] = useState<string | undefined>();
  const navigate = useNavigate();

  useEffect(() => {
    fetchData();
  }, [page, pageSize, status]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const response = await documentApi.list({
        page,
        page_size: pageSize,
        keyword: keyword || undefined,
        status,
      });
      setData(response.data.documents);
      setTotal(response.data.total);
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setPage(1);
    fetchData();
  };

  const columns: ColumnsType<Document> = [
    { title: 'ID', dataIndex: 'id', width: 80 },
    {
      title: '标题',
      dataIndex: 'title',
      ellipsis: true,
      render: (text: string, record: Document) => <a onClick={() => navigate(`/documents/${record.id}`)}>{text}</a>,
    },
    { title: '地区', dataIndex: 'region', width: 100 },
    { title: '年份', dataIndex: 'year', width: 80 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (val: string) => <Tag color={statusColors[val]}>{statusLabels[val]}</Tag>,
    },
    { title: '浏览次数', dataIndex: 'view_count', width: 100 },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 180,
      render: (date: string) => dayjs(date).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: unknown, record: Document) => (
        <Button type="link" icon={<EyeOutlined />} onClick={() => navigate(`/documents/${record.id}`)}>
          查看
        </Button>
      ),
    },
  ];

  return (
    <div>
      <div className="page-header">
        <Title level={4}>文档管理</Title>
      </div>

      <Card>
        <Space style={{ marginBottom: 16 }} wrap>
          <Input
            placeholder="搜索标题或内容"
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 250 }}
          />
          <Select
            placeholder="状态筛选"
            allowClear
            style={{ width: 120 }}
            value={status}
            onChange={setStatus}
            options={[
              { value: 'pending', label: '待审核' },
              { value: 'approved', label: '已通过' },
              { value: 'rejected', label: '已拒绝' },
              { value: 'archived', label: '已归档' },
            ]}
          />
          <Button type="primary" onClick={handleSearch}>搜索</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/upload')}>上传文档</Button>
        </Space>

        <Table
          columns={columns}
          dataSource={data}
          rowKey="id"
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
            },
          }}
        />
      </Card>
    </div>
  );
};

export default Documents;
