import { Typography, Card, Form, Input, Button, message, Avatar, Descriptions, Tag, Upload, Space, Modal, Divider, Tabs, List, Spin } from 'antd';
import { UserOutlined, LockOutlined, HistoryOutlined, EditOutlined, CameraOutlined } from '@ant-design/icons';
import { useState, useEffect } from 'react';
import { useAuthStore } from '../stores/authStore';
import api from '../services/api';

const { Title, Text } = Typography;

interface LoginLog {
  id: number;
  login_time: string;
  ip_address: string;
  user_agent: string;
  latitude?: number;
  longitude?: number;
}

const Profile = () => {
  const { user, updateUser } = useAuthStore();
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [passwordModalVisible, setPasswordModalVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loginLogs, setLoginLogs] = useState<LoginLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [form] = Form.useForm();
  const [passwordForm] = Form.useForm();

  // 获取登录日志
  const fetchLoginLogs = async () => {
    setLogsLoading(true);
    try {
      const response = await api.get('/auth/login-logs');
      setLoginLogs(response.data || []);
    } catch (error) {
      console.error('Failed to fetch login logs:', error);
    } finally {
      setLogsLoading(false);
    }
  };

  useEffect(() => {
    fetchLoginLogs();
  }, []);

  // 打开编辑弹窗
  const handleOpenEdit = () => {
    form.setFieldsValue({
      real_name: user?.real_name,
      email: user?.email,
      phone: user?.phone,
    });
    setEditModalVisible(true);
  };

  // 保存个人信息
  const handleSaveProfile = async (values: any) => {
    setLoading(true);
    try {
      const response = await api.put(`/users/${user?.id}`, values);
      updateUser(response.data);
      message.success('个人信息更新成功');
      setEditModalVisible(false);
    } catch (error) {
      message.error('更新失败');
    } finally {
      setLoading(false);
    }
  };

  // 修改密码
  const handleChangePassword = async (values: any) => {
    if (values.new_password !== values.confirm_password) {
      message.error('两次输入的密码不一致');
      return;
    }
    setLoading(true);
    try {
      await api.post('/auth/change-password', {
        old_password: values.old_password,
        new_password: values.new_password,
      });
      message.success('密码修改成功');
      setPasswordModalVisible(false);
      passwordForm.resetFields();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '密码修改失败');
    } finally {
      setLoading(false);
    }
  };

  // 上传头像
  const handleAvatarUpload = async (file: File) => {
    setAvatarUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await api.post('/users/avatar', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      updateUser({ avatar_url: response.data.avatar_url });
      message.success('头像上传成功');
    } catch (error) {
      message.error('头像上传失败');
    } finally {
      setAvatarUploading(false);
    }
    return false;
  };

  // 角色映射
  const roleLabels: Record<string, { label: string; color: string }> = {
    admin: { label: '管理员', color: 'red' },
    editor: { label: '编辑员', color: 'blue' },
    viewer: { label: '访客', color: 'green' },
    uploader: { label: '上传员', color: 'orange' },
  };

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>个人设置</Title>
      </div>

      <Tabs
        defaultActiveKey="profile"
        items={[
          {
            key: 'profile',
            label: <span><UserOutlined /> 个人信息</span>,
            children: (
              <Card>
                <div style={{ display: 'flex', alignItems: 'flex-start', marginBottom: 32 }}>
                  <div style={{ position: 'relative' }}>
                    <Avatar
                      size={100}
                      icon={<UserOutlined />}
                      src={user?.avatar_url}
                      style={{ backgroundColor: '#1677ff' }}
                    />
                    <Upload
                      showUploadList={false}
                      beforeUpload={handleAvatarUpload}
                      accept="image/*"
                    >
                      <Button
                        type="primary"
                        shape="circle"
                        size="small"
                        icon={avatarUploading ? <Spin size="small" /> : <CameraOutlined />}
                        style={{
                          position: 'absolute',
                          bottom: 0,
                          right: 0,
                        }}
                        disabled={avatarUploading}
                      />
                    </Upload>
                  </div>
                  <div style={{ marginLeft: 24, flex: 1 }}>
                    <Title level={4} style={{ margin: 0 }}>{user?.real_name}</Title>
                    <Text type="secondary">@{user?.username}</Text>
                    <div style={{ marginTop: 16 }}>
                      <Space>
                        <Button type="primary" icon={<EditOutlined />} onClick={handleOpenEdit}>
                          编辑信息
                        </Button>
                        <Button icon={<LockOutlined />} onClick={() => setPasswordModalVisible(true)}>
                          修改密码
                        </Button>
                      </Space>
                    </div>
                  </div>
                </div>

                <Divider />

                <Descriptions column={2} bordered size="small">
                  <Descriptions.Item label="用户名">{user?.username}</Descriptions.Item>
                  <Descriptions.Item label="真实姓名">{user?.real_name}</Descriptions.Item>
                  <Descriptions.Item label="邮箱">{user?.email || '-'}</Descriptions.Item>
                  <Descriptions.Item label="角色">
                    <Tag color={roleLabels[user?.role || '']?.color}>
                      {roleLabels[user?.role || '']?.label || user?.role}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="状态">
                    <Tag color={user?.is_active ? 'green' : 'red'}>
                      {user?.is_active ? '正常' : '禁用'}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="实名认证">
                    <Tag color={user?.is_verified ? 'green' : 'orange'}>
                      {user?.is_verified ? '已认证' : '未认证'}
                    </Tag>
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            ),
          },
          {
            key: 'security',
            label: <span><LockOutlined /> 安全设置</span>,
            children: (
              <Card>
                <List>
                  <List.Item
                    actions={[
                      <Button type="link" onClick={() => setPasswordModalVisible(true)}>
                        修改
                      </Button>,
                    ]}
                  >
                    <List.Item.Meta
                      avatar={<LockOutlined style={{ fontSize: 24, color: '#1677ff' }} />}
                      title="登录密码"
                      description="定期修改密码可以提高账户安全性"
                    />
                  </List.Item>
                </List>
              </Card>
            ),
          },
          {
            key: 'logs',
            label: <span><HistoryOutlined /> 登录日志</span>,
            children: (
              <Card>
                <List
                  loading={logsLoading}
                  dataSource={loginLogs}
                  renderItem={(log) => (
                    <List.Item>
                      <List.Item.Meta
                        title={
                          <Space>
                            <Text>{new Date(log.login_time).toLocaleString('zh-CN')}</Text>
                            {log.latitude && log.longitude && (
                              <Tag color="blue">位置: {log.latitude.toFixed(4)}, {log.longitude.toFixed(4)}</Tag>
                            )}
                          </Space>
                        }
                        description={
                          <Space direction="vertical" size={0}>
                            <Text type="secondary">IP: {log.ip_address}</Text>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              {log.user_agent?.substring(0, 80)}...
                            </Text>
                          </Space>
                        }
                      />
                    </List.Item>
                  )}
                  locale={{ emptyText: '暂无登录记录' }}
                />
              </Card>
            ),
          },
        ]}
      />

      {/* 编辑个人信息弹窗 */}
      <Modal
        title="编辑个人信息"
        open={editModalVisible}
        onCancel={() => setEditModalVisible(false)}
        onOk={() => form.submit()}
        confirmLoading={loading}
      >
        <Form form={form} layout="vertical" onFinish={handleSaveProfile}>
          <Form.Item
            label="真实姓名"
            name="real_name"
            rules={[{ required: true, message: '请输入真实姓名' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            label="邮箱"
            name="email"
            rules={[{ type: 'email', message: '请输入有效邮箱' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item label="手机号" name="phone">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      {/* 修改密码弹窗 */}
      <Modal
        title="修改密码"
        open={passwordModalVisible}
        onCancel={() => { setPasswordModalVisible(false); passwordForm.resetFields(); }}
        onOk={() => passwordForm.submit()}
        confirmLoading={loading}
      >
        <Form form={passwordForm} layout="vertical" onFinish={handleChangePassword}>
          <Form.Item
            label="当前密码"
            name="old_password"
            rules={[{ required: true, message: '请输入当前密码' }]}
          >
            <Input.Password />
          </Form.Item>
          <Form.Item
            label="新密码"
            name="new_password"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 8, message: '密码至少8位' },
              { pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/, message: '密码需包含大小写字母和数字' },
            ]}
          >
            <Input.Password />
          </Form.Item>
          <Form.Item
            label="确认新密码"
            name="confirm_password"
            rules={[
              { required: true, message: '请确认新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('new_password') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'));
                },
              }),
            ]}
          >
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Profile;
