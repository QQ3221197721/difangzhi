import { useState, useEffect } from 'react';
import { Card, Upload, Form, Input, Select, Button, Typography, message, Tabs, Space, Progress, List, Tag, Divider, DatePicker, Row, Col, Alert } from 'antd';
import { InboxOutlined, PlusOutlined, FileTextOutlined, CheckCircleOutlined, LoadingOutlined } from '@ant-design/icons';
import type { UploadProps, UploadFile } from 'antd';
import { documentApi, categoryApi } from '../services/api';
import type { Category } from '../types';

const { Title, Text } = Typography;
const { Dragger } = Upload;
const { TextArea } = Input;
const { Option } = Select;

interface UploadedFile {
  uid: string;
  name: string;
  status: 'uploading' | 'done' | 'error';
  percent?: number;
  response?: any;
}

const UploadPage = () => {
  const [fileForm] = Form.useForm();
  const [manualForm] = Form.useForm();
  const [uploading, setUploading] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [activeTab, setActiveTab] = useState('file');

  // 加载分类
  useEffect(() => {
    categoryApi.list().then(res => setCategories(res.data || []));
  }, []);

  // 文件上传配置
  const uploadProps: UploadProps = {
    name: 'file',
    multiple: true,
    action: '/api/v1/documents/upload',
    accept: '.pdf,.doc,.docx,.xls,.xlsx,.txt,.csv',
    headers: {
      Authorization: `Bearer ${JSON.parse(localStorage.getItem('auth-storage') || '{}')?.state?.accessToken || ''}`,
    },
    data: (file) => {
      const formValues = fileForm.getFieldsValue();
      return {
        region: formValues.region,
        year: formValues.year,
        tags: formValues.tags?.join(','),
        category_ids: formValues.category_ids?.join(','),
      };
    },
    onChange(info) {
      const { status, name, uid, percent, response } = info.file;
      
      setUploadedFiles(prev => {
        const existing = prev.find(f => f.uid === uid);
        if (existing) {
          return prev.map(f => f.uid === uid ? { ...f, status: status as any, percent, response } : f);
        }
        return [...prev, { uid, name, status: status as any, percent, response }];
      });

      if (status === 'done') {
        message.success(`${name} 上传成功，AI正在处理中...`);
      } else if (status === 'error') {
        message.error(`${name} 上传失败`);
      }
    },
    onRemove(file) {
      setUploadedFiles(prev => prev.filter(f => f.uid !== file.uid));
    },
  };

  // 手动录入提交
  const handleManualSubmit = async (values: any) => {
    setUploading(true);
    try {
      await documentApi.create({
        ...values,
        publish_date: values.publish_date?.format('YYYY-MM-DD'),
      });
      message.success('文档创建成功，已提交审核');
      manualForm.resetFields();
    } catch (error) {
      message.error('创建失败，请重试');
    } finally {
      setUploading(false);
    }
  };

  // 地区和年份分类
  const regionCategories = categories.filter(c => c.category_type === 'region');
  const yearCategories = categories.filter(c => c.category_type === 'year');

  const items = [
    {
      key: 'file',
      label: <span><InboxOutlined /> 文件上传（AI提取）</span>,
      children: (
        <Row gutter={24}>
          <Col span={16}>
            <Card>
              <Alert
                message="支持的文件格式"
                description="PDF、Word (.doc/.docx)、Excel (.xls/.xlsx)、文本文件 (.txt)、CSV"
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
              />
              
              <Dragger {...uploadProps} style={{ marginBottom: 24 }}>
                <p className="ant-upload-drag-icon">
                  <InboxOutlined style={{ fontSize: 48, color: '#1677ff' }} />
                </p>
                <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
                <p className="ant-upload-hint">
                  系统会自动提取文件内容，并使用AI生成摘要和关键词
                </p>
              </Dragger>

              <Form form={fileForm} layout="vertical">
                <Row gutter={16}>
                  <Col span={8}>
                    <Form.Item label="地区" name="region">
                      <Select placeholder="选择地区" allowClear showSearch>
                        {regionCategories.map(c => <Option key={c.id} value={c.name}>{c.name}</Option>)}
                      </Select>
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item label="年份" name="year">
                      <Select placeholder="选择年份" allowClear showSearch>
                        {Array.from({ length: 51 }, (_, i) => 2000 + i).map(y => (
                          <Option key={y} value={y}>{y}年</Option>
                        ))}
                      </Select>
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item label="分类" name="category_ids">
                      <Select placeholder="选择分类" mode="multiple" allowClear>
                        {categories.map(c => <Option key={c.id} value={c.id}>{c.name}</Option>)}
                      </Select>
                    </Form.Item>
                  </Col>
                </Row>
                <Form.Item label="标签" name="tags">
                  <Select mode="tags" placeholder="输入标签后按回车添加" />
                </Form.Item>
              </Form>
            </Card>
          </Col>
          
          <Col span={8}>
            <Card title="上传记录" size="small">
              {uploadedFiles.length > 0 ? (
                <List
                  dataSource={uploadedFiles}
                  renderItem={(file) => (
                    <List.Item>
                      <Space style={{ width: '100%' }}>
                        <FileTextOutlined />
                        <Text ellipsis style={{ flex: 1, maxWidth: 150 }}>{file.name}</Text>
                        {file.status === 'uploading' && <LoadingOutlined spin />}
                        {file.status === 'done' && <CheckCircleOutlined style={{ color: '#52c41a' }} />}
                        {file.status === 'error' && <Tag color="error">失败</Tag>}
                      </Space>
                      {file.status === 'uploading' && file.percent !== undefined && (
                        <Progress percent={Math.round(file.percent)} size="small" style={{ marginTop: 4 }} />
                      )}
                    </List.Item>
                  )}
                />
              ) : (
                <Text type="secondary">暂无上传记录</Text>
              )}
            </Card>
          </Col>
        </Row>
      ),
    },
    {
      key: 'manual',
      label: <span><PlusOutlined /> 手动录入</span>,
      children: (
        <Card>
          <Form
            form={manualForm}
            layout="vertical"
            onFinish={handleManualSubmit}
            style={{ maxWidth: 800 }}
          >
            <Form.Item
              label="标题"
              name="title"
              rules={[{ required: true, message: '请输入文档标题' }]}
            >
              <Input placeholder="请输入文档标题" maxLength={200} showCount />
            </Form.Item>

            <Form.Item
              label="内容"
              name="content"
              rules={[{ required: true, message: '请输入文档内容' }]}
            >
              <TextArea
                rows={8}
                placeholder="请输入文档内容..."
                showCount
                maxLength={50000}
              />
            </Form.Item>

            <Row gutter={16}>
              <Col span={8}>
                <Form.Item label="来源" name="source">
                  <Input placeholder="文档来源" />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="作者" name="author">
                  <Input placeholder="作者姓名" />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="发布日期" name="publish_date">
                  <DatePicker style={{ width: '100%' }} />
                </Form.Item>
              </Col>
            </Row>

            <Row gutter={16}>
              <Col span={8}>
                <Form.Item label="地区" name="region">
                  <Select placeholder="选择地区" allowClear showSearch>
                    {regionCategories.map(c => <Option key={c.id} value={c.name}>{c.name}</Option>)}
                  </Select>
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="年份" name="year">
                  <Select placeholder="选择年份" allowClear>
                    {Array.from({ length: 51 }, (_, i) => 2000 + i).map(y => (
                      <Option key={y} value={y}>{y}年</Option>
                    ))}
                  </Select>
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="分类" name="category_ids">
                  <Select placeholder="选择分类" mode="multiple" allowClear>
                    {categories.map(c => <Option key={c.id} value={c.id}>{c.name}</Option>)}
                  </Select>
                </Form.Item>
              </Col>
            </Row>

            <Form.Item label="标签" name="tags">
              <Select mode="tags" placeholder="输入标签后按回车添加" />
            </Form.Item>

            <Divider />

            <Form.Item>
              <Space>
                <Button type="primary" htmlType="submit" loading={uploading} size="large">
                  提交审核
                </Button>
                <Button onClick={() => manualForm.resetFields()}>
                  重置
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>
      ),
    },
  ];

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>数据上传</Title>
        <Text type="secondary">支持文件AI提取和手动录入两种方式</Text>
      </div>
      <Tabs items={items} activeKey={activeTab} onChange={setActiveTab} />
    </div>
  );
};

export default UploadPage;
