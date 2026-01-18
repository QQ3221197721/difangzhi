import { useEffect, useState } from 'react';
import { Row, Col, Card, Statistic, Typography } from 'antd';
import { FileTextOutlined, UserOutlined, CheckCircleOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { analyticsApi } from '../services/api';

const { Title } = Typography;

interface OverviewData {
  documents: { total: number; pending: number; approved: number };
  users: { total: number; active: number };
  categories: number;
  upload_trend: { date: string; count: number }[];
}

const Dashboard = () => {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<OverviewData | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const response = await analyticsApi.overview();
      setData(response.data);
    } catch (error) {
      console.error('Failed to fetch overview:', error);
    } finally {
      setLoading(false);
    }
  };

  const trendOption = {
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: data?.upload_trend.map(item => item.date) || [],
    },
    yAxis: { type: 'value' },
    series: [{
      data: data?.upload_trend.map(item => item.count) || [],
      type: 'line',
      smooth: true,
      areaStyle: { opacity: 0.3 },
      itemStyle: { color: '#1677ff' },
    }],
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  };

  return (
    <div>
      <div className="page-header">
        <Title level={4}>数据概览</Title>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic
              title="文档总数"
              value={data?.documents.total || 0}
              prefix={<FileTextOutlined style={{ color: '#1677ff' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic
              title="待审核"
              value={data?.documents.pending || 0}
              prefix={<FileTextOutlined style={{ color: '#faad14' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic
              title="已通过"
              value={data?.documents.approved || 0}
              prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card loading={loading}>
            <Statistic
              title="用户数"
              value={data?.users.total || 0}
              prefix={<UserOutlined style={{ color: '#722ed1' }} />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={16}>
          <Card title="近7天上传趋势" loading={loading}>
            <ReactECharts option={trendOption} style={{ height: 300 }} />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card title="快捷操作" loading={loading}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <Card.Grid style={{ width: '100%', textAlign: 'center', cursor: 'pointer' }}
                onClick={() => window.location.href = '/upload'}>
                上传文档
              </Card.Grid>
              <Card.Grid style={{ width: '100%', textAlign: 'center', cursor: 'pointer' }}
                onClick={() => window.location.href = '/search'}>
                智能搜索
              </Card.Grid>
              <Card.Grid style={{ width: '100%', textAlign: 'center', cursor: 'pointer' }}
                onClick={() => window.location.href = '/ai-chat'}>
                AI 助手
              </Card.Grid>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
