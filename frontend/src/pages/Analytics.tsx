import React, { useEffect, useState } from 'react';
import { Typography, Card, Row, Col, Statistic, DatePicker, Spin, Space, Segmented } from 'antd';
import { FileTextOutlined, UserOutlined, TagsOutlined, RiseOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { analyticsApi } from '../services/api';
import type { Dayjs } from 'dayjs';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

interface OverviewData {
  documents: { total: number; pending: number; approved: number };
  users: { total: number; active: number };
  categories: number;
  upload_trend: { date: string; count: number }[];
}

const Analytics: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [regionData, setRegionData] = useState<Array<{ region: string; count: number }>>([]);
  const [yearData, setYearData] = useState<Array<{ year: number; count: number }>>([]);
  const [categoryData, setCategoryData] = useState<Array<{ category_type: string; count: number }>>([]);
  const [trendData, setTrendData] = useState<Array<{ date: string; count: number }>>([]);
  const [chartType, setChartType] = useState<string>('bar');
  const [timeRange, setTimeRange] = useState<[Dayjs, Dayjs] | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [overviewRes, regionRes, yearRes, categoryRes, trendRes] = await Promise.all([
        analyticsApi.overview(),
        analyticsApi.byRegion(),
        analyticsApi.byYear(),
        analyticsApi.byCategory(),
        analyticsApi.uploadTrend({ days: 30 }),
      ]);
      setOverview(overviewRes.data);
      setRegionData(regionRes.data?.data || []);
      setYearData(yearRes.data?.data || []);
      setCategoryData(categoryRes.data?.data || []);
      setTrendData(trendRes.data?.data || []);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  const regionBarOption = {
    tooltip: { trigger: 'axis' as const, axisPointer: { type: 'shadow' as const } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category' as const, data: regionData.map((d) => d.region), axisLabel: { rotate: 30 } },
    yAxis: { type: 'value' as const, name: '文档数量' },
    series: [
      {
        name: '文档数量',
        type: 'bar' as const,
        data: regionData.map((d) => d.count),
        itemStyle: { color: '#1677ff', borderRadius: [4, 4, 0, 0] },
      },
    ],
  };

  const regionPieOption = {
    tooltip: { trigger: 'item' as const, formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'vertical' as const, right: 10, top: 'center' },
    series: [
      {
        name: '地区分布',
        type: 'pie' as const,
        radius: ['40%', '70%'],
        data: regionData.map((d) => ({ name: d.region, value: d.count })),
      },
    ],
  };

  const yearOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category' as const, data: yearData.map((d) => d.year), boundaryGap: false },
    yAxis: { type: 'value' as const, name: '文档数量' },
    series: [
      {
        name: '文档数量',
        type: 'line' as const,
        smooth: true,
        data: yearData.map((d) => d.count),
        areaStyle: { opacity: 0.3 },
        itemStyle: { color: '#1677ff' },
      },
    ],
  };

  const categoryOption = {
    tooltip: { trigger: 'item' as const, formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'horizontal' as const, bottom: 0 },
    series: [
      {
        name: '分类占比',
        type: 'pie' as const,
        radius: '65%',
        center: ['50%', '45%'],
        data: categoryData.map((d) => ({ name: d.category_type, value: d.count })),
      },
    ],
  };

  const trendOption = {
    tooltip: { trigger: 'axis' as const, axisPointer: { type: 'cross' as const } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category' as const, data: trendData.map((d) => d.date), boundaryGap: false },
    yAxis: { type: 'value' as const, name: '上传数量' },
    series: [
      {
        name: '上传数量',
        type: 'line' as const,
        smooth: true,
        data: trendData.map((d) => d.count),
        areaStyle: { opacity: 0.2, color: '#52c41a' },
        lineStyle: { color: '#52c41a' },
        itemStyle: { color: '#52c41a' },
      },
    ],
  };

  const statusOption = {
    tooltip: { trigger: 'item' as const },
    legend: { bottom: 0 },
    series: [
      {
        name: '状态分布',
        type: 'pie' as const,
        radius: ['50%', '70%'],
        center: ['50%', '45%'],
        label: { show: true, position: 'center' as const, formatter: overview ? `总计\n${overview.documents.total}` : '' },
        data: overview
          ? [
              { value: overview.documents.approved, name: '已审核', itemStyle: { color: '#52c41a' } },
              { value: overview.documents.pending, name: '待审核', itemStyle: { color: '#faad14' } },
              { value: overview.documents.total - overview.documents.approved - overview.documents.pending, name: '已拒绝', itemStyle: { color: '#ff4d4f' } },
            ]
          : [],
      },
    ],
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>数据分析</Title>
        <Space>
          <RangePicker value={timeRange} onChange={(dates) => setTimeRange(dates as [Dayjs, Dayjs])} placeholder={['开始日期', '结束日期']} />
        </Space>
      </div>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic title="文档总数" value={overview?.documents.total || 0} prefix={<FileTextOutlined style={{ color: '#1677ff' }} />} suffix={<Text type="secondary" style={{ fontSize: 14 }}> 篇</Text>} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="待审核" value={overview?.documents.pending || 0} prefix={<RiseOutlined style={{ color: '#faad14' }} />} valueStyle={{ color: '#faad14' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="用户数量" value={overview?.users.total || 0} prefix={<UserOutlined style={{ color: '#52c41a' }} />} suffix={<Text type="secondary" style={{ fontSize: 14 }}> / {overview?.users.active || 0} 活跃</Text>} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="分类标签" value={overview?.categories || 0} prefix={<TagsOutlined style={{ color: '#722ed1' }} />} />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={12}>
          <Card title="地区分布" extra={<Segmented size="small" options={[{ value: 'bar', label: '柱状图' }, { value: 'pie', label: '饼图' }]} value={chartType} onChange={(v) => setChartType(v as string)} />}>
            <ReactECharts option={chartType === 'bar' ? regionBarOption : regionPieOption} style={{ height: 320 }} />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="年份趋势">
            <ReactECharts option={yearOption} style={{ height: 320 }} />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={8}>
          <Card title="文档状态分布">
            <ReactECharts option={statusOption} style={{ height: 280 }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card title="分类占比">
            <ReactECharts option={categoryOption} style={{ height: 280 }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card title="近30天上传趋势">
            <ReactECharts option={trendOption} style={{ height: 280 }} />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Analytics;
