import React, { useState, useEffect } from 'react';
import { 
  Card, Upload as AntUpload, Button, Tabs, Form, Input, Select, 
  InputNumber, Table, Tag, Space, message, Progress, Modal, Typography,
  Row, Col, Divider, Alert
} from 'antd';
import { 
  InboxOutlined, FileTextOutlined, TableOutlined, 
  CloudUploadOutlined, CheckCircleOutlined, LoadingOutlined,
  PlusOutlined, DeleteOutlined
} from '@ant-design/icons';
import { uploadService } from '../services/api';

const { Dragger } = AntUpload;
const { TextArea } = Input;
const { Title, Text } = Typography;

const Upload = () => {
  const [activeTab, setActiveTab] = useState('file');
  const [fileList, setFileList] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadHistory, setUploadHistory] = useState([]);
  const [manualForm] = Form.useForm();
  const [batchData, setBatchData] = useState([]);

  // 工作类别选项
  const workCategories = ['农业', '工业', '服务业', '科技', '教育', '医疗', '金融', '交通', '建筑', '其他'];

  // 获取上传历史
  useEffect(() => {
    fetchUploadHistory();
  }, []);

  const fetchUploadHistory = async () => {
    try {
      const response = await uploadService.getUploadHistory();
      setUploadHistory(response.data);
    } catch (error) {
      console.error('获取上传历史失败:', error);
    }
  };

  // 文件上传配置
  const uploadProps = {
    name: 'file',
    multiple: false,
    accept: '.pdf,.txt,.doc,.docx',
    fileList,
    beforeUpload: (file) => {
      const isValidType = ['application/pdf', 'text/plain', 
        'application/msword', 
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      ].includes(file.type);
      
      if (!isValidType) {
        message.error('只支持PDF、TXT、DOC、DOCX格式文件');
        return false;
      }
      
      const isLt50M = file.size / 1024 / 1024 < 50;
      if (!isLt50M) {
        message.error('文件大小不能超过50MB');
        return false;
      }
      
      setFileList([file]);
      return false;
    },
    onRemove: () => {
      setFileList([]);
    },
  };

  // 表格上传配置
  const spreadsheetProps = {
    name: 'file',
    multiple: false,
    accept: '.xlsx,.xls,.csv',
    beforeUpload: async (file) => {
      const isValidType = [
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel',
        'text/csv'
      ].includes(file.type) || file.name.endsWith('.csv');
      
      if (!isValidType) {
        message.error('只支持Excel或CSV格式文件');
        return false;
      }
      
      setUploading(true);
      try {
        const response = await uploadService.uploadSpreadsheet(file, (percent) => {
          console.log('上传进度:', percent);
        });
        message.success('表格上传成功，正在处理中...');
        fetchUploadHistory();
      } catch (error) {
        message.error('上传失败');
      } finally {
        setUploading(false);
      }
      
      return false;
    },
  };

  // 上传文件
  const handleUpload = async () => {
    if (fileList.length === 0) {
      message.warning('请先选择文件');
      return;
    }
    
    setUploading(true);
    try {
      const response = await uploadService.uploadFile(fileList[0], (percent) => {
        console.log('上传进度:', percent);
      });
      message.success('文件上传成功，AI正在提取数据...');
      setFileList([]);
      fetchUploadHistory();
    } catch (error) {
      message.error('上传失败');
    } finally {
      setUploading(false);
    }
  };

  // 手动提交数据
  const handleManualSubmit = async (values) => {
    try {
      await uploadService.uploadManualData(values);
      message.success('数据提交成功');
      manualForm.resetFields();
    } catch (error) {
      message.error('提交失败');
    }
  };

  // 批量提交数据
  const handleBatchSubmit = async () => {
    if (batchData.length === 0) {
      message.warning('请先添加数据');
      return;
    }
    
    try {
      await uploadService.uploadBatchData({ records: batchData });
      message.success(`成功提交 ${batchData.length} 条数据`);
      setBatchData([]);
    } catch (error) {
      message.error('批量提交失败');
    }
  };

  // 历史记录表格列
  const historyColumns = [
    {
      title: '文件名',
      dataIndex: 'original_filename',
      key: 'original_filename',
      ellipsis: true,
    },
    {
      title: '类型',
      dataIndex: 'file_type',
      key: 'file_type',
      width: 80,
      render: (type) => <Tag>{type.toUpperCase()}</Tag>,
    },
    {
      title: '大小',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 100,
      render: (size) => `${(size / 1024).toFixed(2)} KB`,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status) => {
        const statusMap = {
          pending: { color: 'default', text: '等待中' },
          processing: { color: 'processing', text: '处理中' },
          completed: { color: 'success', text: '已完成' },
          failed: { color: 'error', text: '失败' },
        };
        const { color, text } = statusMap[status] || { color: 'default', text: status };
        return <Tag color={color}>{text}</Tag>;
      },
    },
    {
      title: '上传时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (time) => new Date(time).toLocaleString(),
    },
  ];

  // 文件上传Tab
  const FileUploadTab = () => (
    <div>
      <Alert
        message="AI智能提取"
        description="上传PDF、TXT、DOC格式的地方志文件，系统将使用AI自动提取数据并分类"
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />
      
      <Dragger {...uploadProps} style={{ marginBottom: 16 }}>
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
        <p className="ant-upload-hint">支持PDF、TXT、DOC、DOCX格式，最大50MB</p>
      </Dragger>
      
      <Button
        type="primary"
        onClick={handleUpload}
        loading={uploading}
        disabled={fileList.length === 0}
        icon={<CloudUploadOutlined />}
        block
      >
        开始上传并提取
      </Button>
    </div>
  );

  // 表格上传Tab
  const SpreadsheetUploadTab = () => (
    <div>
      <Alert
        message="表格数据导入"
        description="上传已处理好的Excel或CSV表格，系统将自动解析并存入数据库"
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />
      
      <Dragger {...spreadsheetProps}>
        <p className="ant-upload-drag-icon">
          <TableOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽表格文件到此区域上传</p>
        <p className="ant-upload-hint">支持XLSX、XLS、CSV格式</p>
      </Dragger>
      
      <Divider />
      
      <Title level={5}>表格格式要求</Title>
      <Text type="secondary">
        表格需包含以下列：标题、内容、地区、省份、城市、区县、年份、单位、人物、收入、工作类别
      </Text>
    </div>
  );

  // 手动输入Tab
  const ManualInputTab = () => (
    <Form form={manualForm} onFinish={handleManualSubmit} layout="vertical">
      <Row gutter={16}>
        <Col span={24}>
          <Form.Item name="title" label="标题" rules={[{ required: true }]}>
            <Input placeholder="请输入数据标题" />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="region_province" label="省份">
            <Input placeholder="如：辽宁省" />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="region_city" label="城市">
            <Input placeholder="如：葫芦岛市" />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="year" label="年份">
            <InputNumber min={2000} max={2050} style={{ width: '100%' }} placeholder="年份" />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="work_category" label="工作类别">
            <Select placeholder="选择工作类别">
              {workCategories.map(cat => (
                <Select.Option key={cat} value={cat}>{cat}</Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="unit" label="单位">
            <Input placeholder="相关单位名称" />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="income" label="收入（万元）">
            <InputNumber min={0} style={{ width: '100%' }} placeholder="收入金额" />
          </Form.Item>
        </Col>
        <Col span={24}>
          <Form.Item name="content" label="内容">
            <TextArea rows={4} placeholder="详细内容" />
          </Form.Item>
        </Col>
      </Row>
      <Form.Item>
        <Button type="primary" htmlType="submit" block>
          提交数据
        </Button>
      </Form.Item>
    </Form>
  );

  const tabItems = [
    { key: 'file', label: <><FileTextOutlined /> 文件上传</>, children: <FileUploadTab /> },
    { key: 'spreadsheet', label: <><TableOutlined /> 表格导入</>, children: <SpreadsheetUploadTab /> },
    { key: 'manual', label: <><PlusOutlined /> 手动输入</>, children: <ManualInputTab /> },
  ];

  return (
    <div>
      <Title level={4}>数据上传</Title>
      <Text type="secondary" style={{ marginBottom: 24, display: 'block' }}>
        支持AI智能提取和手动上传两种方式
      </Text>
      
      <Row gutter={16}>
        <Col xs={24} lg={14}>
          <Card>
            <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="上传历史" extra={<Button type="link" onClick={fetchUploadHistory}>刷新</Button>}>
            <Table
              columns={historyColumns}
              dataSource={uploadHistory}
              rowKey="id"
              size="small"
              pagination={{ pageSize: 5 }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Upload;
