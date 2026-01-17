import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Table, Tag, Space, Progress, Typography } from 'antd';
import {
  FileTextOutlined,
  SearchOutlined,
  RiseOutlined,
  TeamOutlined,
  CloudUploadOutlined,
  DatabaseOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';

const { Title, Text } = Typography;

const Dashboard = () => {
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState({
    totalRecords: 12580,
    totalFiles: 156,
    todayUploads: 23,
    activeUsers: 89,
  });

  // 模拟数据 - 实际应从API获取
  const recentUploads = [
    { id: 1, name: '辽宁省2023年工业发展报告.pdf', status: 'completed', records: 45, time: '10分钟前' },
    { id: 2, name: '葫芦岛市经济统计.xlsx', status: 'processing', records: 0, time: '30分钟前' },
    { id: 3, name: '锦州市农业数据.doc', status: 'completed', records: 32, time: '1小时前' },
    { id: 4, name: '大连市2022年年鉴.pdf', status: 'completed', records: 128, time: '2小时前' },
  ];

  const columns = [
    {
      title: '文件名',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => (
        <Tag color={status === 'completed' ? 'green' : status === 'processing' ? 'blue' : 'red'}>
          {status === 'completed' ? '已完成' : status === 'processing' ? '处理中' : '失败'}
        </Tag>
      ),
    },
    {
      title: '提取记录数',
      dataIndex: 'records',
      key: 'records',
    },
    {
      title: '上传时间',
      dataIndex: 'time',
      key: 'time',
    },
  ];

  // 地区分布图表配置
  const regionChartOption = {
    tooltip: {
      trigger: 'item',
    },
    legend: {
      orient: 'vertical',
      left: 'left',
    },
    series: [
      {
        name: '数据分布',
        type: 'pie',
        radius: '50%',
        data: [
          { value: 3500, name: '沈阳市' },
          { value: 2800, name: '大连市' },
          { value: 1800, name: '鞍山市' },
          { value: 1500, name: '葫芦岛市' },
          { value: 2980, name: '其他' },
        ],
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
          },
        },
      },
    ],
  };

  // 趋势图表配置
  const trendChartOption = {
    tooltip: {
      trigger: 'axis',
    },
    legend: {
      data: ['数据量', '上传量'],
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: ['1月', '2月', '3月', '4月', '5月', '6月', '7月'],
    },
    yAxis: {
      type: 'value',
    },
    series: [
      {
        name: '数据量',
        type: 'line',
        smooth: true,
        data: [1200, 2300, 3400, 4500, 5600, 8900, 12580],
        areaStyle: {
          color: 'rgba(24, 144, 255, 0.2)',
        },
      },
      {
        name: '上传量',
        type: 'line',
        smooth: true,
        data: [20, 35, 42, 58, 76, 120, 156],
      },
    ],
  };

  // 工作类别分布
  const categoryChartOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
      },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: ['工业', '农业', '服务业', '科技', '教育', '医疗', '金融'],
    },
    yAxis: {
      type: 'value',
    },
    series: [
      {
        data: [3200, 2800, 2100, 1800, 1200, 900, 580],
        type: 'bar',
        itemStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: '#1890ff' },
              { offset: 1, color: '#69c0ff' },
            ],
          },
        },
      },
    ],
  };

  return (
    <div>
      <Title level={4}>控制台</Title>
      <Text type="secondary" style={{ marginBottom: 24, display: 'block' }}>
        欢迎使用地方志数据管理系统
      </Text>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="总数据量"
              value={stats.totalRecords}
              prefix={<DatabaseOutlined style={{ color: '#1890ff' }} />}
              suffix="条"
            />
            <Progress percent={75} showInfo={false} strokeColor="#1890ff" />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="文件总数"
              value={stats.totalFiles}
              prefix={<FileTextOutlined style={{ color: '#52c41a' }} />}
              suffix="个"
            />
            <Progress percent={60} showInfo={false} strokeColor="#52c41a" />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="今日上传"
              value={stats.todayUploads}
              prefix={<CloudUploadOutlined style={{ color: '#faad14' }} />}
              suffix="次"
            />
            <Progress percent={45} showInfo={false} strokeColor="#faad14" />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card>
            <Statistic
              title="活跃用户"
              value={stats.activeUsers}
              prefix={<TeamOutlined style={{ color: '#722ed1' }} />}
              suffix="人"
            />
            <Progress percent={85} showInfo={false} strokeColor="#722ed1" />
          </Card>
        </Col>
      </Row>

      {/* 图表区域 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="数据增长趋势">
            <ReactECharts option={trendChartOption} style={{ height: 300 }} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="地区数据分布">
            <ReactECharts option={regionChartOption} style={{ height: 300 }} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="工作类别分布">
            <ReactECharts option={categoryChartOption} style={{ height: 300 }} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="最近上传">
            <Table
              columns={columns}
              dataSource={recentUploads}
              rowKey="id"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
