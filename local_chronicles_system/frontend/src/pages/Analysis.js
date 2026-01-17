import React, { useState, useEffect } from 'react';
import {
  Card, Row, Col, Select, Button, Tabs, Typography, Spin, Empty,
  Table, Statistic, Space, message, Form, Radio
} from 'antd';
import {
  BarChartOutlined, LineChartOutlined, PieChartOutlined,
  DotChartOutlined, HeatMapOutlined, TableOutlined,
  DownloadOutlined, ReloadOutlined
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { analysisService } from '../services/api';

const { Title, Text, Paragraph } = Typography;

const Analysis = () => {
  const [loading, setLoading] = useState(false);
  const [recordIds, setRecordIds] = useState([]);
  const [summaryData, setSummaryData] = useState(null);
  const [chartImage, setChartImage] = useState(null);
  const [chartType, setChartType] = useState('bar');
  const [xField, setXField] = useState('region_city');
  const [yField, setYField] = useState('income');
  const [groupField, setGroupField] = useState(null);

  // 字段选项
  const fieldOptions = [
    { value: 'region_city', label: '城市' },
    { value: 'year', label: '年份' },
    { value: 'work_category', label: '工作类别' },
    { value: 'unit', label: '单位' },
    { value: 'income', label: '收入' },
  ];

  // 图表类型
  const chartTypes = [
    { value: 'bar', label: '柱状图', icon: <BarChartOutlined /> },
    { value: 'line', label: '折线图', icon: <LineChartOutlined /> },
    { value: 'pie', label: '饼图', icon: <PieChartOutlined /> },
    { value: 'scatter', label: '散点图', icon: <DotChartOutlined /> },
    { value: 'heatmap', label: '热力图', icon: <HeatMapOutlined /> },
  ];

  useEffect(() => {
    // 从localStorage获取选中的记录ID
    const storedIds = localStorage.getItem('analysisRecordIds');
    if (storedIds) {
      const ids = JSON.parse(storedIds);
      setRecordIds(ids);
      if (ids.length > 0) {
        fetchSummary(ids);
      }
    }
  }, []);

  // 获取数据汇总
  const fetchSummary = async (ids) => {
    setLoading(true);
    try {
      const response = await analysisService.getSummary(ids);
      setSummaryData(response.data.data);
    } catch (error) {
      message.error('获取数据汇总失败');
    } finally {
      setLoading(false);
    }
  };

  // 生成可视化图表
  const generateChart = async () => {
    if (recordIds.length === 0) {
      message.warning('请先选择要分析的数据');
      return;
    }

    setLoading(true);
    try {
      const response = await analysisService.createVisualization(
        recordIds, chartType, xField, yField, groupField, null
      );
      setChartImage(response.data.image_base64);
      message.success('图表生成成功');
    } catch (error) {
      message.error('图表生成失败');
    } finally {
      setLoading(false);
    }
  };

  // 导出数据
  const handleExport = async (type) => {
    if (recordIds.length === 0) {
      message.warning('没有可导出的数据');
      return;
    }

    try {
      const response = type === 'excel'
        ? await analysisService.exportExcel(recordIds)
        : await analysisService.exportCSV(recordIds);

      const blob = new Blob([response.data]);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `analysis_export.${type === 'excel' ? 'xlsx' : 'csv'}`;
      link.click();
      window.URL.revokeObjectURL(url);
      message.success('导出成功');
    } catch (error) {
      message.error('导出失败');
    }
  };

  // 汇总统计卡片
  const SummaryCards = () => {
    if (!summaryData) return <Empty description="暂无数据" />;

    return (
      <Row gutter={[16, 16]}>
        <Col xs={12} sm={8} lg={4}>
          <Card>
            <Statistic title="总记录数" value={summaryData.total_records} />
          </Card>
        </Col>
        {summaryData.income_stats && (
          <>
            <Col xs={12} sm={8} lg={4}>
              <Card>
                <Statistic 
                  title="平均收入" 
                  value={summaryData.income_stats.mean?.toFixed(2)} 
                  suffix="万元" 
                />
              </Card>
            </Col>
            <Col xs={12} sm={8} lg={4}>
              <Card>
                <Statistic 
                  title="收入中位数" 
                  value={summaryData.income_stats.median?.toFixed(2)} 
                  suffix="万元" 
                />
              </Card>
            </Col>
            <Col xs={12} sm={8} lg={4}>
              <Card>
                <Statistic 
                  title="最高收入" 
                  value={summaryData.income_stats.max?.toFixed(2)} 
                  suffix="万元" 
                />
              </Card>
            </Col>
            <Col xs={12} sm={8} lg={4}>
              <Card>
                <Statistic 
                  title="收入总和" 
                  value={summaryData.income_stats.sum?.toFixed(2)} 
                  suffix="万元" 
                />
              </Card>
            </Col>
          </>
        )}
      </Row>
    );
  };

  // 分布图表
  const DistributionCharts = () => {
    if (!summaryData) return null;

    const workCategoryOption = summaryData.work_category_distribution ? {
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: '60%',
        data: Object.entries(summaryData.work_category_distribution).map(([name, value]) => ({
          name, value
        })),
      }],
    } : null;

    const regionOption = summaryData.region_distribution ? {
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: Object.keys(summaryData.region_distribution),
        axisLabel: { rotate: 45 },
      },
      yAxis: { type: 'value' },
      series: [{
        data: Object.values(summaryData.region_distribution),
        type: 'bar',
        itemStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: '#1890ff' },
              { offset: 1, color: '#69c0ff' },
            ],
          },
        },
      }],
    } : null;

    const yearOption = summaryData.year_distribution ? {
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: Object.keys(summaryData.year_distribution),
      },
      yAxis: { type: 'value' },
      series: [{
        data: Object.values(summaryData.year_distribution),
        type: 'line',
        smooth: true,
        areaStyle: { color: 'rgba(24, 144, 255, 0.2)' },
      }],
    } : null;

    return (
      <Row gutter={[16, 16]}>
        {workCategoryOption && (
          <Col xs={24} lg={8}>
            <Card title="工作类别分布">
              <ReactECharts option={workCategoryOption} style={{ height: 300 }} />
            </Card>
          </Col>
        )}
        {regionOption && (
          <Col xs={24} lg={8}>
            <Card title="地区分布">
              <ReactECharts option={regionOption} style={{ height: 300 }} />
            </Card>
          </Col>
        )}
        {yearOption && (
          <Col xs={24} lg={8}>
            <Card title="年份分布">
              <ReactECharts option={yearOption} style={{ height: 300 }} />
            </Card>
          </Col>
        )}
      </Row>
    );
  };

  // 自定义图表
  const CustomChart = () => (
    <Card title="自定义可视化">
      <Form layout="inline" style={{ marginBottom: 16 }}>
        <Form.Item label="图表类型">
          <Radio.Group value={chartType} onChange={e => setChartType(e.target.value)}>
            {chartTypes.map(type => (
              <Radio.Button key={type.value} value={type.value}>
                {type.icon} {type.label}
              </Radio.Button>
            ))}
          </Radio.Group>
        </Form.Item>
      </Form>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Select
            value={xField}
            onChange={setXField}
            style={{ width: '100%' }}
            placeholder="X轴字段"
            options={fieldOptions}
          />
        </Col>
        <Col span={6}>
          <Select
            value={yField}
            onChange={setYField}
            style={{ width: '100%' }}
            placeholder="Y轴字段"
            options={fieldOptions}
          />
        </Col>
        <Col span={6}>
          <Select
            value={groupField}
            onChange={setGroupField}
            style={{ width: '100%' }}
            placeholder="分组字段（可选）"
            allowClear
            options={fieldOptions}
          />
        </Col>
        <Col span={6}>
          <Button type="primary" onClick={generateChart} loading={loading}>
            生成图表
          </Button>
        </Col>
      </Row>

      {chartImage && (
        <div style={{ textAlign: 'center' }}>
          <img
            src={`data:image/png;base64,${chartImage}`}
            alt="Chart"
            style={{ maxWidth: '100%', border: '1px solid #f0f0f0' }}
          />
        </div>
      )}
    </Card>
  );

  return (
    <div>
      <Title level={4}>数据分析</Title>
      <Text type="secondary" style={{ marginBottom: 24, display: 'block' }}>
        使用pandas进行数据分析，matplotlib进行可视化绘图
      </Text>

      <Space style={{ marginBottom: 16 }}>
        <Text>当前分析数据：{recordIds.length} 条</Text>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => fetchSummary(recordIds)}
          disabled={recordIds.length === 0}
        >
          刷新分析
        </Button>
        <Button
          icon={<DownloadOutlined />}
          onClick={() => handleExport('excel')}
          disabled={recordIds.length === 0}
        >
          导出Excel
        </Button>
        <Button
          onClick={() => handleExport('csv')}
          disabled={recordIds.length === 0}
        >
          导出CSV
        </Button>
      </Space>

      <Spin spinning={loading}>
        {/* 汇总统计 */}
        <Card title="数据汇总" style={{ marginBottom: 16 }}>
          <SummaryCards />
        </Card>

        {/* 分布图表 */}
        <div style={{ marginBottom: 16 }}>
          <DistributionCharts />
        </div>

        {/* 自定义图表 */}
        <CustomChart />
      </Spin>
    </div>
  );
};

export default Analysis;
