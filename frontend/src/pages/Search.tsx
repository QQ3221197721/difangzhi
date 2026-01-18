import { useState, useEffect } from 'react';
import { Card, Input, Button, List, Typography, Tag, Tabs, Space, Empty, Spin, Select, Row, Col, Rate, Divider, message } from 'antd';
import { SearchOutlined, RobotOutlined, TagOutlined, FileTextOutlined, EnvironmentOutlined, CalendarOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { aiApi, documentApi, categoryApi } from '../services/api';
import type { Document, Category } from '../types';

const { Title, Text, Paragraph } = Typography;
const { Search } = Input;
const { Option } = Select;

interface AISearchResult {
  answer: string;
  sources: Document[];
  confidence: number;
}

const SearchPage = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [aiResult, setAiResult] = useState<AISearchResult | null>(null);
  const [normalResults, setNormalResults] = useState<Document[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [total, setTotal] = useState(0);
  
  // 筛选条件
  const [filters, setFilters] = useState({
    keyword: '',
    region: undefined as string | undefined,
    yearStart: undefined as number | undefined,
    yearEnd: undefined as number | undefined,
    categoryIds: [] as number[],
    status: 'approved' as string,
  });

  // 获取分类
  useEffect(() => {
    categoryApi.list().then(res => setCategories(res.data || []));
  }, []);

  // AI搜索
  const handleAISearch = async (value: string) => {
    if (!value.trim()) {
      message.warning('请输入搜索内容');
      return;
    }
    setLoading(true);
    setAiResult(null);
    try {
      const response = await aiApi.search({ question: value, top_k: 10 });
      setAiResult(response.data);
    } catch (error) {
      message.error('AI搜索失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  // 普通搜索
  const handleNormalSearch = async () => {
    setLoading(true);
    try {
      const params: any = {
        page: 1,
        page_size: 50,
        status: filters.status,
      };
      if (filters.keyword) params.keyword = filters.keyword;
      if (filters.region) params.region = filters.region;
      if (filters.yearStart) params.year_start = filters.yearStart;
      if (filters.yearEnd) params.year_end = filters.yearEnd;
      if (filters.categoryIds.length > 0) params.category_ids = filters.categoryIds.join(',');

      const response = await documentApi.list(params);
      setNormalResults(response.data.documents || response.data || []);
      setTotal(response.data.total || 0);
    } catch (error) {
      message.error('搜索失败');
    } finally {
      setLoading(false);
    }
  };

  // 重置筛选
  const handleReset = () => {
    setFilters({
      keyword: '',
      region: undefined,
      yearStart: undefined,
      yearEnd: undefined,
      categoryIds: [],
      status: 'approved',
    });
    setNormalResults([]);
    setTotal(0);
  };

  // 地区列表
  const regions = [...new Set(categories.filter(c => c.category_type === 'region').map(c => c.name))];
  // 年份列表
  const years = Array.from({ length: 51 }, (_, i) => 2000 + i);

  const items = [
    {
      key: 'ai',
      label: <span><RobotOutlined /> AI智能搜索</span>,
      children: (
        <div>
          <Card style={{ marginBottom: 24 }}>
            <Search
              placeholder="用自然语言描述您想查找的内容，例如：查找关于上海地区的历史资料..."
              enterButton="AI搜索"
              size="large"
              onSearch={handleAISearch}
              loading={loading}
              allowClear
            />
            <div style={{ marginTop: 12, color: '#999' }}>
              <Text type="secondary">提示：AI会理解您的问题并从地方志数据库中找到相关内容</Text>
            </div>
          </Card>

          {loading && (
            <div style={{ textAlign: 'center', padding: 60 }}>
              <Spin size="large" tip="AI正在分析您的问题..." />
            </div>
          )}

          {aiResult && !loading && (
            <>
              <Card title="AI 回答" style={{ marginBottom: 16 }}>
                <Paragraph style={{ fontSize: 16, lineHeight: 1.8 }}>
                  {aiResult.answer}
                </Paragraph>
                <Divider />
                <Space>
                  <Text type="secondary">置信度：</Text>
                  <Rate disabled value={Math.round(aiResult.confidence * 5)} count={5} />
                  <Text type="secondary">({(aiResult.confidence * 100).toFixed(1)}%)</Text>
                </Space>
              </Card>

              {aiResult.sources?.length > 0 && (
                <Card title={`相关文档 (${aiResult.sources.length})`}>
                  <List
                    dataSource={aiResult.sources}
                    renderItem={(item: Document) => (
                      <List.Item
                        actions={[
                          <Button type="link" onClick={() => navigate(`/documents/${item.id}`)}>
                            查看详情
                          </Button>,
                        ]}
                      >
                        <List.Item.Meta
                          avatar={<FileTextOutlined style={{ fontSize: 24, color: '#1677ff' }} />}
                          title={<a onClick={() => navigate(`/documents/${item.id}`)}>{item.title}</a>}
                          description={
                            <Space direction="vertical" size={4}>
                              <Text ellipsis style={{ maxWidth: 600 }}>
                                {item.content?.substring(0, 150) || item.ai_summary?.substring(0, 150)}...
                              </Text>
                              <Space size="small">
                                {item.region && <Tag icon={<EnvironmentOutlined />}>{item.region}</Tag>}
                                {item.year && <Tag icon={<CalendarOutlined />}>{item.year}年</Tag>}
                                {item.tags?.slice(0, 3).map((tag, i) => <Tag key={i}>{tag}</Tag>)}
                              </Space>
                            </Space>
                          }
                        />
                      </List.Item>
                    )}
                  />
                </Card>
              )}
            </>
          )}

          {!aiResult && !loading && (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="输入您的问题，AI将帮您找到答案"
            />
          )}
        </div>
      ),
    },
    {
      key: 'normal',
      label: <span><TagOutlined /> 标签筛选搜索</span>,
      children: (
        <div>
          <Card style={{ marginBottom: 16 }}>
            <Row gutter={[16, 16]}>
              <Col span={8}>
                <Input
                  placeholder="关键词搜索"
                  prefix={<SearchOutlined />}
                  value={filters.keyword}
                  onChange={(e) => setFilters(prev => ({ ...prev, keyword: e.target.value }))}
                  onPressEnter={handleNormalSearch}
                  allowClear
                />
              </Col>
              <Col span={4}>
                <Select
                  placeholder="选择地区"
                  style={{ width: '100%' }}
                  value={filters.region}
                  onChange={(v) => setFilters(prev => ({ ...prev, region: v }))}
                  allowClear
                >
                  {regions.map(r => <Option key={r} value={r}>{r}</Option>)}
                </Select>
              </Col>
              <Col span={3}>
                <Select
                  placeholder="起始年"
                  style={{ width: '100%' }}
                  value={filters.yearStart}
                  onChange={(v) => setFilters(prev => ({ ...prev, yearStart: v }))}
                  allowClear
                >
                  {years.map(y => <Option key={y} value={y}>{y}</Option>)}
                </Select>
              </Col>
              <Col span={3}>
                <Select
                  placeholder="结束年"
                  style={{ width: '100%' }}
                  value={filters.yearEnd}
                  onChange={(v) => setFilters(prev => ({ ...prev, yearEnd: v }))}
                  allowClear
                >
                  {years.map(y => <Option key={y} value={y}>{y}</Option>)}
                </Select>
              </Col>
              <Col span={6}>
                <Space>
                  <Button type="primary" icon={<SearchOutlined />} onClick={handleNormalSearch} loading={loading}>
                    搜索
                  </Button>
                  <Button onClick={handleReset}>重置</Button>
                </Space>
              </Col>
            </Row>
          </Card>

          {total > 0 && (
            <div style={{ marginBottom: 16 }}>
              <Text type="secondary">找到 {total} 条结果</Text>
            </div>
          )}

          {normalResults.length > 0 ? (
            <List
              dataSource={normalResults}
              loading={loading}
              pagination={{
                pageSize: 10,
                showSizeChanger: true,
                showTotal: (t) => `共 ${t} 条`,
              }}
              renderItem={(item: Document) => (
                <Card style={{ marginBottom: 12 }} hoverable onClick={() => navigate(`/documents/${item.id}`)}>
                  <List.Item.Meta
                    avatar={<FileTextOutlined style={{ fontSize: 32, color: '#1677ff' }} />}
                    title={<Text strong style={{ fontSize: 16 }}>{item.title}</Text>}
                    description={
                      <Space direction="vertical" size={8} style={{ width: '100%' }}>
                        <Paragraph ellipsis={{ rows: 2 }} style={{ margin: 0, color: '#666' }}>
                          {item.ai_summary || item.content?.substring(0, 200)}
                        </Paragraph>
                        <Space wrap>
                          {item.region && <Tag color="blue" icon={<EnvironmentOutlined />}>{item.region}</Tag>}
                          {item.year && <Tag color="green" icon={<CalendarOutlined />}>{item.year}年</Tag>}
                          {item.author && <Tag>作者: {item.author}</Tag>}
                          {item.tags?.slice(0, 5).map((tag, i) => <Tag key={i}>{tag}</Tag>)}
                        </Space>
                      </Space>
                    }
                  />
                </Card>
              )}
            />
          ) : (
            <Empty description={loading ? '搜索中...' : '请输入搜索条件'} />
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>智能搜索</Title>
        <Text type="secondary">支持AI语义搜索和传统关键词搜索</Text>
      </div>
      <Tabs items={items} />
    </div>
  );
};

export default SearchPage;
