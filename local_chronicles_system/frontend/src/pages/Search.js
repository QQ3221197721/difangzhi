import React, { useState, useEffect } from 'react';
import {
  Card, Input, Button, Table, Tag, Space, Tabs, Form, Select,
  Row, Col, Slider, Typography, Drawer, Descriptions, message,
  InputNumber, Cascader, Checkbox, Empty
} from 'antd';
import {
  SearchOutlined, FilterOutlined, RobotOutlined,
  ExportOutlined, EyeOutlined, BarChartOutlined
} from '@ant-design/icons';
import { searchService, analysisService } from '../services/api';
import { useNavigate } from 'react-router-dom';

const { Title, Text, Paragraph } = Typography;
const { Search } = Input;

const SearchPage = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('ai');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [selectedRows, setSelectedRows] = useState([]);
  const [categories, setCategories] = useState(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [currentRecord, setCurrentRecord] = useState(null);
  const [filterForm] = Form.useForm();

  // 工作类别
  const workCategories = ['农业', '工业', '服务业', '科技', '教育', '医疗', '金融', '交通', '建筑', '其他'];

  // 获取分类数据
  useEffect(() => {
    fetchCategories();
  }, []);

  const fetchCategories = async () => {
    try {
      const response = await searchService.getCategories();
      setCategories(response.data.data);
    } catch (error) {
      console.error('获取分类失败:', error);
    }
  };

  // AI智能搜索
  const handleAISearch = async (query) => {
    if (!query.trim()) {
      message.warning('请输入搜索内容');
      return;
    }

    setLoading(true);
    try {
      const response = await searchService.aiSearch(query, 50);
      setResults(response.data.results);
      setTotal(response.data.total);
      message.success(`搜索完成，耗时 ${response.data.execution_time_ms}ms`);
    } catch (error) {
      message.error('搜索失败');
    } finally {
      setLoading(false);
    }
  };

  // 筛选搜索
  const handleFilterSearch = async (values) => {
    setLoading(true);
    try {
      const filters = {
        region: values.region,
        region_province: values.region_province,
        region_city: values.region_city,
        year_start: values.year_range?.[0],
        year_end: values.year_range?.[1],
        work_category: values.work_category,
        unit: values.unit,
        income_min: values.income_range?.[0],
        income_max: values.income_range?.[1],
      };

      const response = await searchService.filterSearch(filters, page, pageSize);
      setResults(response.data.results);
      setTotal(response.data.total);
      message.success(`找到 ${response.data.total} 条数据，耗时 ${response.data.execution_time_ms}ms`);
    } catch (error) {
      message.error('搜索失败');
    } finally {
      setLoading(false);
    }
  };

  // 查看详情
  const handleViewDetail = async (record) => {
    setCurrentRecord(record);
    setDetailVisible(true);
  };

  // 导出选中数据
  const handleExport = async (type) => {
    if (selectedRows.length === 0) {
      message.warning('请先选择要导出的数据');
      return;
    }

    try {
      const recordIds = selectedRows.map(r => r.id);
      const response = type === 'excel'
        ? await analysisService.exportExcel(recordIds)
        : await analysisService.exportCSV(recordIds);

      const blob = new Blob([response.data]);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `data_export.${type === 'excel' ? 'xlsx' : 'csv'}`;
      link.click();
      window.URL.revokeObjectURL(url);
      message.success('导出成功');
    } catch (error) {
      message.error('导出失败');
    }
  };

  // 跳转到分析页面
  const handleAnalyze = () => {
    if (selectedRows.length === 0) {
      message.warning('请先选择要分析的数据');
      return;
    }
    // 存储选中的记录ID
    localStorage.setItem('analysisRecordIds', JSON.stringify(selectedRows.map(r => r.id)));
    navigate('/analysis');
  };

  // 表格列配置
  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      width: 250,
      ellipsis: true,
      render: (text, record) => (
        <a onClick={() => handleViewDetail(record)}>{text}</a>
      ),
    },
    {
      title: '地区',
      dataIndex: 'region_city',
      key: 'region_city',
      width: 120,
      render: (text, record) => text || record.region || '-',
    },
    {
      title: '年份',
      dataIndex: 'year',
      key: 'year',
      width: 80,
    },
    {
      title: '工作类别',
      dataIndex: 'work_category',
      key: 'work_category',
      width: 100,
      render: (text) => text ? <Tag color="blue">{text}</Tag> : '-',
    },
    {
      title: '收入(万元)',
      dataIndex: 'income',
      key: 'income',
      width: 100,
      render: (value) => value ? value.toLocaleString() : '-',
    },
    {
      title: '置信度',
      dataIndex: 'confidence_score',
      key: 'confidence_score',
      width: 80,
      render: (value) => (
        <Tag color={value >= 0.8 ? 'green' : value >= 0.5 ? 'orange' : 'red'}>
          {(value * 100).toFixed(0)}%
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_, record) => (
        <Button type="link" icon={<EyeOutlined />} onClick={() => handleViewDetail(record)}>
          详情
        </Button>
      ),
    },
  ];

  // AI搜索Tab
  const AISearchTab = () => (
    <div>
      <Search
        placeholder="输入自然语言查询，如：查找2020年葫芦岛市的工业数据"
        enterButton={<><RobotOutlined /> AI智能搜索</>}
        size="large"
        onSearch={handleAISearch}
        loading={loading}
        style={{ marginBottom: 16 }}
      />
      <Text type="secondary">
        示例：「辽宁省2020-2023年农业发展数据」「葫芦岛市工业企业收入超过100万的记录」
      </Text>
    </div>
  );

  // 筛选搜索Tab
  const FilterSearchTab = () => (
    <Form form={filterForm} onFinish={handleFilterSearch} layout="vertical">
      <Row gutter={16}>
        <Col span={8}>
          <Form.Item name="region" label="地区">
            <Input placeholder="输入地区名称，如：辽宁葫芦岛市" />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="region_province" label="省份">
            <Select placeholder="选择省份" allowClear>
              {categories?.values?.['地区'] && Object.keys(categories.values['地区']).map(province => (
                <Select.Option key={province} value={province}>{province}</Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="region_city" label="城市">
            <Select placeholder="选择城市" allowClear>
              {categories?.values?.['地区'] && Object.values(categories.values['地区']).flat().map(city => (
                <Select.Option key={city} value={city}>{city}</Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="year_range" label="年份范围">
            <Slider
              range
              min={categories?.values?.['年份']?.min || 2000}
              max={categories?.values?.['年份']?.max || 2050}
              defaultValue={[2015, 2025]}
            />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="work_category" label="工作类别">
            <Select placeholder="选择工作类别" allowClear>
              {workCategories.map(cat => (
                <Select.Option key={cat} value={cat}>{cat}</Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="unit" label="单位">
            <Input placeholder="输入单位名称" />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="income_range" label="收入范围（万元）">
            <Space>
              <InputNumber min={0} placeholder="最小" style={{ width: 120 }} />
              <span>-</span>
              <InputNumber min={0} placeholder="最大" style={{ width: 120 }} />
            </Space>
          </Form.Item>
        </Col>
      </Row>
      <Form.Item>
        <Space>
          <Button type="primary" htmlType="submit" icon={<FilterOutlined />} loading={loading}>
            筛选搜索
          </Button>
          <Button onClick={() => filterForm.resetFields()}>重置</Button>
        </Space>
      </Form.Item>
    </Form>
  );

  const tabItems = [
    { key: 'ai', label: <><RobotOutlined /> AI智能搜索</>, children: <AISearchTab /> },
    { key: 'filter', label: <><FilterOutlined /> 标签筛选</>, children: <FilterSearchTab /> },
  ];

  const rowSelection = {
    selectedRowKeys: selectedRows.map(r => r.id),
    onChange: (_, rows) => setSelectedRows(rows),
  };

  return (
    <div>
      <Title level={4}>数据搜索</Title>
      <Text type="secondary" style={{ marginBottom: 24, display: 'block' }}>
        支持AI智能搜索和标签筛选两种模式
      </Text>

      <Card style={{ marginBottom: 16 }}>
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
      </Card>

      {/* 操作栏 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space>
          <Text>已选择 {selectedRows.length} 条数据</Text>
          <Button icon={<BarChartOutlined />} onClick={handleAnalyze} disabled={selectedRows.length === 0}>
            数据分析
          </Button>
          <Button icon={<ExportOutlined />} onClick={() => handleExport('excel')} disabled={selectedRows.length === 0}>
            导出Excel
          </Button>
          <Button onClick={() => handleExport('csv')} disabled={selectedRows.length === 0}>
            导出CSV
          </Button>
        </Space>
      </Card>

      {/* 结果表格 */}
      <Card>
        <Table
          columns={columns}
          dataSource={results}
          rowKey="id"
          loading={loading}
          rowSelection={rowSelection}
          pagination={{
            current: page,
            pageSize: pageSize,
            total: total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条数据`,
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
            },
          }}
          locale={{ emptyText: <Empty description="暂无数据，请先进行搜索" /> }}
        />
      </Card>

      {/* 详情抽屉 */}
      <Drawer
        title="数据详情"
        placement="right"
        width={600}
        open={detailVisible}
        onClose={() => setDetailVisible(false)}
      >
        {currentRecord && (
          <Descriptions bordered column={1}>
            <Descriptions.Item label="标题">{currentRecord.title}</Descriptions.Item>
            <Descriptions.Item label="地区">{currentRecord.region || currentRecord.region_city || '-'}</Descriptions.Item>
            <Descriptions.Item label="年份">{currentRecord.year || '-'}</Descriptions.Item>
            <Descriptions.Item label="工作类别">{currentRecord.work_category || '-'}</Descriptions.Item>
            <Descriptions.Item label="单位">{currentRecord.unit || '-'}</Descriptions.Item>
            <Descriptions.Item label="人物">{currentRecord.person || '-'}</Descriptions.Item>
            <Descriptions.Item label="收入">{currentRecord.income ? `${currentRecord.income}万元` : '-'}</Descriptions.Item>
            <Descriptions.Item label="摘要">{currentRecord.summary || '-'}</Descriptions.Item>
            <Descriptions.Item label="内容">
              <Paragraph ellipsis={{ rows: 10, expandable: true }}>
                {currentRecord.content || '-'}
              </Paragraph>
            </Descriptions.Item>
            <Descriptions.Item label="置信度">
              <Tag color={currentRecord.confidence_score >= 0.8 ? 'green' : 'orange'}>
                {(currentRecord.confidence_score * 100).toFixed(0)}%
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="标签">
              {currentRecord.tags && Object.entries(currentRecord.tags).map(([key, value]) => (
                <Tag key={key}>{key}: {value}</Tag>
              ))}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
};

export default SearchPage;
