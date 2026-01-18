import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Descriptions, Tag, Button, Space, Typography, Spin, Divider, message, Modal, Input, Select } from 'antd';
import { ArrowLeftOutlined, DownloadOutlined, DeleteOutlined, CheckOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { documentApi } from '../services/api';
import { useAuthStore } from '../stores/authStore';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

interface DocumentData {
  id: number;
  title: string;
  content?: string;
  full_text?: string;
  source?: string;
  author?: string;
  publish_date?: string;
  file_path?: string;
  file_name?: string;
  file_size?: number;
  file_type?: string;
  region?: string;
  year?: number;
  tags: string[];
  ai_summary?: string;
  ai_keywords?: string[];
  status: string;
  upload_type: string;
  uploader_id: number;
  view_count: number;
  download_count: number;
  created_at: string;
  updated_at: string;
  download_url?: string;
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

const DocumentDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [doc, setDoc] = useState<DocumentData | null>(null);
  const [reviewModalVisible, setReviewModalVisible] = useState(false);
  const [reviewStatus, setReviewStatus] = useState<string>('');
  const [reviewComment, setReviewComment] = useState('');

  useEffect(() => {
    if (id) fetchDocument();
  }, [id]);

  const fetchDocument = async () => {
    setLoading(true);
    try {
      const response = await documentApi.get(Number(id));
      setDoc(response.data);
    } catch {
      message.error('获取文档失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    try {
      const response = await documentApi.get(Number(id));
      if (response.data.download_url) {
        window.open(response.data.download_url, '_blank');
      } else {
        message.warning('文件不可下载');
      }
    } catch {
      message.error('下载失败');
    }
  };

  const handleDelete = () => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个文档吗？此操作不可恢复。',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await documentApi.delete(Number(id));
          message.success('删除成功');
          navigate('/documents');
        } catch {
          message.error('删除失败');
        }
      },
    });
  };

  const handleReview = async () => {
    if (!reviewStatus) {
      message.warning('请选择审核状态');
      return;
    }
    try {
      await documentApi.review(Number(id), { status: reviewStatus, comment: reviewComment });
      message.success('审核成功');
      setReviewModalVisible(false);
      fetchDocument();
    } catch {
      message.error('审核失败');
    }
  };

  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return '-';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!doc) {
    return <div style={{ textAlign: 'center', padding: 100 }}>文档不存在</div>;
  }

  const isAdmin = user?.role === 'admin';

  const headerSection = (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
      <div>
        <Title level={3} style={{ margin: 0 }}>{doc.title}</Title>
        <Space style={{ marginTop: 8 }}>
          <Tag color={statusColors[doc.status]}>{statusLabels[doc.status]}</Tag>
          <Text type="secondary">浏览: {doc.view_count}</Text>
          <Text type="secondary">下载: {doc.download_count}</Text>
        </Space>
      </div>
      <Space>
        {doc.file_path && <Button icon={<DownloadOutlined />} onClick={handleDownload}>下载</Button>}
        {isAdmin && doc.status === 'pending' && (
          <Button type="primary" icon={<CheckOutlined />} onClick={() => setReviewModalVisible(true)}>审核</Button>
        )}
        {isAdmin && <Button danger icon={<DeleteOutlined />} onClick={handleDelete}>删除</Button>}
      </Space>
    </div>
  );

  const infoSection = (
    <Descriptions bordered column={2}>
      <Descriptions.Item label="地区">{doc.region || '-'}</Descriptions.Item>
      <Descriptions.Item label="年份">{doc.year || '-'}</Descriptions.Item>
      <Descriptions.Item label="来源">{doc.source || '-'}</Descriptions.Item>
      <Descriptions.Item label="作者">{doc.author || '-'}</Descriptions.Item>
      <Descriptions.Item label="上传方式">{doc.upload_type === 'file' ? '文件上传' : '手动录入'}</Descriptions.Item>
      <Descriptions.Item label="文件类型">{doc.file_type || '-'}</Descriptions.Item>
      <Descriptions.Item label="文件大小">{formatFileSize(doc.file_size)}</Descriptions.Item>
      <Descriptions.Item label="创建时间">{dayjs(doc.created_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
      <Descriptions.Item label="标签" span={2}>
        {doc.tags?.length > 0 ? doc.tags.map((tag) => <Tag key={tag}>{tag}</Tag>) : '-'}
      </Descriptions.Item>
    </Descriptions>
  );

  const aiSummarySection = doc.ai_summary && (
    <>
      <Divider orientation="left">AI 摘要</Divider>
      <Card type="inner" style={{ background: '#f6ffed' }}>
        <Paragraph>{doc.ai_summary}</Paragraph>
        {doc.ai_keywords && doc.ai_keywords.length > 0 && (
          <div>
            <Text strong>关键词：</Text>
            {doc.ai_keywords.map((kw) => <Tag key={kw} color="blue">{kw}</Tag>)}
          </div>
        )}
      </Card>
    </>
  );

  const contentSection = (
    <>
      <Divider orientation="left">文档内容</Divider>
      <Card type="inner">
        <Paragraph style={{ whiteSpace: 'pre-wrap' }}>
          {doc.full_text || doc.content || '暂无内容'}
        </Paragraph>
      </Card>
    </>
  );

  const reviewModal = (
    <Modal
      title="文档审核"
      open={reviewModalVisible}
      onCancel={() => setReviewModalVisible(false)}
      onOk={handleReview}
      okText="提交"
      cancelText="取消"
    >
      <div style={{ marginBottom: 16 }}>
        <Text>审核状态：</Text>
        <Select
          style={{ width: '100%', marginTop: 8 }}
          placeholder="选择审核状态"
          value={reviewStatus}
          onChange={setReviewStatus}
          options={[
            { value: 'approved', label: '通过' },
            { value: 'rejected', label: '拒绝' },
          ]}
        />
      </div>
      <div>
        <Text>审核意见：</Text>
        <TextArea
          style={{ marginTop: 8 }}
          rows={4}
          placeholder="请输入审核意见..."
          value={reviewComment}
          onChange={(e) => setReviewComment(e.target.value)}
        />
      </div>
    </Modal>
  );

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/documents')}>返回列表</Button>
      </div>

      <Card>
        {headerSection}
        {infoSection}
        {aiSummarySection}
        {contentSection}
      </Card>

      {reviewModal}
    </div>
  );
};

export default DocumentDetail;
