import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Form, Input, Button, Card, Tabs, message, Modal, Steps, Alert } from 'antd';
import { UserOutlined, LockOutlined, MailOutlined, IdcardOutlined, PhoneOutlined, EnvironmentOutlined } from '@ant-design/icons';
import { authService } from '../services/api';
import './Login.css';

const { Step } = Steps;

const Login = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('login');
  const [verifyModalVisible, setVerifyModalVisible] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [locationGranted, setLocationGranted] = useState(false);
  const [location, setLocation] = useState(null);

  // 获取位置信息
  const getLocation = () => {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error('浏览器不支持地理位置'));
        return;
      }
      
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const loc = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
          };
          setLocation(loc);
          setLocationGranted(true);
          resolve(loc);
        },
        (error) => {
          reject(error);
        },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    });
  };

  // 登录处理
  const handleLogin = async (values) => {
    setLoading(true);
    try {
      // 先获取位置
      let loc = location;
      if (!loc) {
        try {
          loc = await getLocation();
        } catch (err) {
          message.error('请授权位置信息访问后再登录');
          setLoading(false);
          return;
        }
      }
      
      const response = await authService.login({
        username: values.username,
        password: values.password,
        location: loc,
      });
      
      const { access_token, refresh_token } = response.data;
      localStorage.setItem('token', access_token);
      localStorage.setItem('refreshToken', refresh_token);
      
      message.success('登录成功');
      navigate('/dashboard');
    } catch (error) {
      if (error.response?.headers?.['x-require-verification']) {
        setVerifyModalVisible(true);
      }
    } finally {
      setLoading(false);
    }
  };

  // 注册处理
  const handleRegister = async (values) => {
    setLoading(true);
    try {
      await authService.register(values);
      message.success('注册成功，请完成实名认证');
      setVerifyModalVisible(true);
    } catch (error) {
      // 错误已由拦截器处理
    } finally {
      setLoading(false);
    }
  };

  // 实名认证处理
  const handleVerify = async (values) => {
    setLoading(true);
    try {
      await authService.verifyIdentity(values);
      message.success('实名认证成功');
      setVerifyModalVisible(false);
      setActiveTab('login');
    } catch (error) {
      // 错误已由拦截器处理
    } finally {
      setLoading(false);
    }
  };

  // 登录表单
  const LoginForm = () => (
    <Form onFinish={handleLogin} size="large">
      <Form.Item
        name="username"
        rules={[{ required: true, message: '请输入用户名' }]}
      >
        <Input prefix={<UserOutlined />} placeholder="用户名" />
      </Form.Item>
      <Form.Item
        name="password"
        rules={[{ required: true, message: '请输入密码' }]}
      >
        <Input.Password prefix={<LockOutlined />} placeholder="密码" />
      </Form.Item>
      
      <Alert
        message="登录需要授权位置信息"
        description={locationGranted ? '位置已获取' : '点击下方按钮授权位置'}
        type={locationGranted ? 'success' : 'info'}
        showIcon
        icon={<EnvironmentOutlined />}
        style={{ marginBottom: 16 }}
        action={
          !locationGranted && (
            <Button size="small" onClick={getLocation}>
              授权位置
            </Button>
          )
        }
      />
      
      <Form.Item>
        <Button type="primary" htmlType="submit" block loading={loading}>
          登录
        </Button>
      </Form.Item>
    </Form>
  );

  // 注册表单
  const RegisterForm = () => (
    <Form onFinish={handleRegister} size="large">
      <Form.Item
        name="username"
        rules={[
          { required: true, message: '请输入用户名' },
          { min: 3, message: '用户名至少3个字符' },
        ]}
      >
        <Input prefix={<UserOutlined />} placeholder="用户名" />
      </Form.Item>
      <Form.Item
        name="email"
        rules={[
          { required: true, message: '请输入邮箱' },
          { type: 'email', message: '邮箱格式不正确' },
        ]}
      >
        <Input prefix={<MailOutlined />} placeholder="邮箱" />
      </Form.Item>
      <Form.Item
        name="password"
        rules={[
          { required: true, message: '请输入密码' },
          { min: 8, message: '密码至少8个字符' },
        ]}
      >
        <Input.Password prefix={<LockOutlined />} placeholder="密码" />
      </Form.Item>
      <Form.Item
        name="confirm_password"
        dependencies={['password']}
        rules={[
          { required: true, message: '请确认密码' },
          ({ getFieldValue }) => ({
            validator(_, value) {
              if (!value || getFieldValue('password') === value) {
                return Promise.resolve();
              }
              return Promise.reject(new Error('两次密码不一致'));
            },
          }),
        ]}
      >
        <Input.Password prefix={<LockOutlined />} placeholder="确认密码" />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit" block loading={loading}>
          注册
        </Button>
      </Form.Item>
    </Form>
  );

  // 实名认证表单
  const VerificationForm = () => (
    <Form onFinish={handleVerify} size="large">
      <Steps current={currentStep} style={{ marginBottom: 24 }}>
        <Step title="身份信息" />
        <Step title="验证完成" />
      </Steps>
      
      <Form.Item
        name="real_name"
        rules={[{ required: true, message: '请输入真实姓名' }]}
      >
        <Input prefix={<UserOutlined />} placeholder="真实姓名" />
      </Form.Item>
      <Form.Item
        name="id_card"
        rules={[
          { required: true, message: '请输入身份证号' },
          { len: 18, message: '身份证号必须为18位' },
        ]}
      >
        <Input prefix={<IdcardOutlined />} placeholder="身份证号" maxLength={18} />
      </Form.Item>
      <Form.Item
        name="phone"
        rules={[
          { required: true, message: '请输入手机号' },
          { pattern: /^1[3-9]\d{9}$/, message: '手机号格式不正确' },
        ]}
      >
        <Input prefix={<PhoneOutlined />} placeholder="手机号" maxLength={11} />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit" block loading={loading}>
          提交认证
        </Button>
      </Form.Item>
    </Form>
  );

  const tabItems = [
    { key: 'login', label: '登录', children: <LoginForm /> },
    { key: 'register', label: '注册', children: <RegisterForm /> },
  ];

  return (
    <div className="login-container">
      <div className="login-background" />
      <Card className="login-card" bordered={false}>
        <div className="login-logo">
          <h1>地方志数据管理系统</h1>
          <p>智能数据提取与分析平台</p>
        </div>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
          centered
        />
      </Card>
      
      <Modal
        title="实名认证"
        open={verifyModalVisible}
        onCancel={() => setVerifyModalVisible(false)}
        footer={null}
        width={400}
      >
        <Alert
          message="实名认证提示"
          description="根据相关规定，使用本系统需要完成实名认证。您的信息将被加密存储。"
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
        <VerificationForm />
      </Modal>
    </div>
  );
};

export default Login;
