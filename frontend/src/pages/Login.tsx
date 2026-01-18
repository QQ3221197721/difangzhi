import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Form, Input, Button, Card, Typography, message, Space, Spin, Tabs, Divider } from 'antd';
import { UserOutlined, LockOutlined, EnvironmentOutlined, MailOutlined, PhoneOutlined, IdcardOutlined } from '@ant-design/icons';
import { useAuthStore } from '../stores/authStore';
import api from '../services/api';

const { Title, Text } = Typography;

const Login: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [locationLoading, setLocationLoading] = useState(true);
  const [location, setLocation] = useState<{ latitude: number; longitude: number } | null>(null);
  const [activeTab, setActiveTab] = useState('login');
  const navigate = useNavigate();
  const { login, isAuthenticated } = useAuthStore();
  const [loginForm] = Form.useForm();
  const [registerForm] = Form.useForm();

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard');
    }
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setLocation({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          });
          setLocationLoading(false);
        },
        () => {
          message.warning('无法获取位置信息，部分功能可能受限');
          setLocationLoading(false);
        },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    } else {
      message.warning('浏览器不支持位置服务');
      setLocationLoading(false);
    }
  }, []);

  const handleLogin = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      await login(values.username, values.password, location || undefined);
      message.success('登录成功');
      navigate('/dashboard');
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error.response?.data?.detail || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (values: Record<string, string>) => {
    if (values.password !== values.confirmPassword) {
      message.error('两次输入的密码不一致');
      return;
    }
    setLoading(true);
    try {
      await api.post('/auth/register', {
        username: values.username,
        password: values.password,
        real_name: values.real_name,
        email: values.email,
        phone: values.phone,
        id_card: values.id_card,
      });
      message.success('注册成功，请登录');
      setActiveTab('login');
      registerForm.resetFields();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      message.error(error.response?.data?.detail || '注册失败');
    } finally {
      setLoading(false);
    }
  };

  const LocationStatus: React.FC = () => (
    <Space>
      <EnvironmentOutlined />
      {locationLoading ? (
        <Spin size="small" />
      ) : location ? (
        <Text type="success">位置已获取</Text>
      ) : (
        <Text type="warning">位置未获取</Text>
      )}
    </Space>
  );

  const loginTabContent = (
    <Form form={loginForm} name="login" onFinish={handleLogin} size="large" autoComplete="off">
      <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
        <Input prefix={<UserOutlined />} placeholder="用户名" />
      </Form.Item>
      <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
        <Input.Password prefix={<LockOutlined />} placeholder="密码" />
      </Form.Item>
      <Form.Item>
        <LocationStatus />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit" loading={loading} block>
          登录
        </Button>
      </Form.Item>
    </Form>
  );

  const registerTabContent = (
    <Form form={registerForm} name="register" onFinish={handleRegister} size="large" autoComplete="off">
      <Form.Item
        name="username"
        rules={[
          { required: true, message: '请输入用户名' },
          { min: 3, message: '用户名至少3个字符' },
        ]}
      >
        <Input prefix={<UserOutlined />} placeholder="用户名" />
      </Form.Item>
      <Form.Item name="real_name" rules={[{ required: true, message: '请输入真实姓名' }]}>
        <Input prefix={<IdcardOutlined />} placeholder="真实姓名" />
      </Form.Item>
      <Form.Item
        name="email"
        rules={[
          { required: true, message: '请输入邮箱' },
          { type: 'email', message: '请输入有效邮箱' },
        ]}
      >
        <Input prefix={<MailOutlined />} placeholder="邮箱" />
      </Form.Item>
      <Form.Item name="phone">
        <Input prefix={<PhoneOutlined />} placeholder="手机号（可选）" />
      </Form.Item>
      <Form.Item
        name="password"
        rules={[
          { required: true, message: '请输入密码' },
          { min: 8, message: '密码至少8位' },
        ]}
      >
        <Input.Password prefix={<LockOutlined />} placeholder="密码（至少8位）" />
      </Form.Item>
      <Form.Item
        name="confirmPassword"
        rules={[
          { required: true, message: '请确认密码' },
          ({ getFieldValue }) => ({
            validator(_, value) {
              if (!value || getFieldValue('password') === value) {
                return Promise.resolve();
              }
              return Promise.reject(new Error('两次输入的密码不一致'));
            },
          }),
        ]}
      >
        <Input.Password prefix={<LockOutlined />} placeholder="确认密码" />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit" loading={loading} block>
          注册
        </Button>
      </Form.Item>
    </Form>
  );

  const tabItems = [
    { key: 'login', label: '登录', children: loginTabContent },
    { key: 'register', label: '注册', children: registerTabContent },
  ];

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      }}
    >
      <Card style={{ width: 440, borderRadius: 12, boxShadow: '0 8px 24px rgba(0,0,0,0.15)' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Title level={3} style={{ marginBottom: 8 }}>
            地方志数据管理系统
          </Title>
          <Text type="secondary">智能化地方志数据管理平台</Text>
        </div>

        <Tabs activeKey={activeTab} onChange={setActiveTab} centered items={tabItems} />

        <Divider style={{ margin: '12px 0' }} />

        <div style={{ textAlign: 'center' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            本系统需要采集您的位置信息用于安全审计
          </Text>
        </div>
      </Card>
    </div>
  );
};

export default Login;
