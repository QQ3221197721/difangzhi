import { Typography, Table, Tag, Button, Space, Card, Input, Select, Modal, Form, message, Popconfirm, Avatar, Tooltip, Switch } from 'antd';
import { SearchOutlined, UserOutlined, EditOutlined, LockOutlined, ReloadOutlined } from '@ant-design/icons';
import { useEffect, useState, useCallback } from 'react';
import { userApi } from '../services/api';
import type { User } from '../types';
import { useDebounce } from '../hooks';

const { Title } = Typography;
const { Option } = Select;

interface UserFilters {
  keyword: string;
  role: string;
  status: string;
}

const Users = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState<UserFilters>({ keyword: '', role: '', status: '' });
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [roleModalVisible, setRoleModalVisible] = useState(false);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [form] = Form.useForm();
  const [roleForm] = Form.useForm();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });

  const debouncedKeyword = useDebounce(filters.keyword, 500);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = {
        page: pagination.current,
        page_size: pagination.pageSize,
      };
      if (debouncedKeyword) params.keyword = debouncedKeyword;
      if (filters.role) params.role = filters.role;
      if (filters.status === 'active') params.is_active = true;
      if (filters.status === 'inactive') params.is_active = false;

      const response = await userApi.list(params);
      setUsers(response.data.data || response.data || []);
      setPagination(prev => ({ ...prev, total: response.data.total || 0 }));
    } catch (error) {
      console.error('Failed to fetch users:', error);
    } finally {
      setLoading(false);
    }
  }, [pagination.current, pagination.pageSize, debouncedKeyword, filters.role, filters.status]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // 切换用户状态
  const handleToggleStatus = async (user: User) => {
    try {
      await userApi.updateStatus(user.id, !user.is_active);
      message.success(`用户已${user.is_active ? '禁用' : '启用'}`);
      fetchUsers();
    } catch (error) {
      message.error('操作失败');
    }
  };

  // 打开角色修改弹窗
  const handleEditRole = (user: User) => {
    setCurrentUser(user);
    roleForm.setFieldsValue({ role: user.role });
    setRoleModalVisible(true);
  };

  // 修改角色
  const handleRoleSubmit = async (values: { role: string }) => {
    if (!currentUser) return;
    try {
      await userApi.updateRole(currentUser.id, values.role);
      message.success('角色修改成功');
      setRoleModalVisible(false);
      fetchUsers();
    } catch (error) {
      message.error('修改失败');
    }
  };

  // 打开编辑弹窗
  const handleEdit = (user: User) => {
    setCurrentUser(user);
    form.setFieldsValue(user);
    setEditModalVisible(true);
  };

  // 编辑用户信息
  const handleEditSubmit = async (values: any) => {
    if (!currentUser) return;
    try {
      await userApi.update(currentUser.id, values);
      message.success('修改成功');
      setEditModalVisible(false);
      fetchUsers();
    } catch (error) {
      message.error('修改失败');
    }
  };

  const roleColors: Record<string, string> = {
    admin: 'red',
    editor: 'blue',
    viewer: 'green',
    uploader: 'orange',
  };

  const roleLabels: Record<string, string> = {
    admin: '管理员',
    editor: '编辑员',
    viewer: '访客',
    uploader: '上传员',
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      width: 60,
    },
    {
      title: '用户',
      key: 'user',
      width: 200,
      render: (_: any, record: User) => (
        <Space>
          <Avatar icon={<UserOutlined />} src={record.avatar_url} style={{ backgroundColor: '#1677ff' }} />
          <div>
            <div style={{ fontWeight: 500 }}>{record.real_name}</div>
            <div style={{ fontSize: 12, color: '#999' }}>@{record.username}</div>
          </div>
        </Space>
      ),
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      width: 200,
    },
    {
      title: '角色',
      dataIndex: 'role',
      width: 100,
      render: (role: string) => (
        <Tag color={roleColors[role] || 'default'}>{roleLabels[role] || role}</Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 80,
      render: (active: boolean, record: User) => (
        <Switch
          checked={active}
          checkedChildren="启用"
          unCheckedChildren="禁用"
          onChange={() => handleToggleStatus(record)}
        />
      ),
    },
    {
      title: '实名认证',
      dataIndex: 'is_verified',
      width: 100,
      render: (verified: boolean) => (
        <Tag color={verified ? 'green' : 'orange'}>{verified ? '已认证' : '未认证'}</Tag>
      ),
    },
    {
      title: '注册时间',
      dataIndex: 'created_at',
      width: 180,
      render: (date: string) => date ? new Date(date).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      fixed: 'right' as const,
      render: (_: any, record: User) => (
        <Space size="small">
          <Tooltip title="编辑信息">
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
          </Tooltip>
          <Tooltip title="修改角色">
            <Button type="text" size="small" icon={<LockOutlined />} onClick={() => handleEditRole(record)} />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>用户管理</Title>
        <Button icon={<ReloadOutlined />} onClick={fetchUsers}>刷新</Button>
      </div>

      {/* 筛选栏 */}
      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Input
            placeholder="搜索用户名/姓名/邮箱"
            prefix={<SearchOutlined />}
            style={{ width: 240 }}
            value={filters.keyword}
            onChange={(e) => setFilters(prev => ({ ...prev, keyword: e.target.value }))}
            allowClear
          />
          <Select
            placeholder="角色筛选"
            style={{ width: 120 }}
            value={filters.role || undefined}
            onChange={(value) => setFilters(prev => ({ ...prev, role: value }))}
            allowClear
          >
            <Option value="admin">管理员</Option>
            <Option value="editor">编辑员</Option>
            <Option value="viewer">访客</Option>
            <Option value="uploader">上传员</Option>
          </Select>
          <Select
            placeholder="状态筛选"
            style={{ width: 120 }}
            value={filters.status || undefined}
            onChange={(value) => setFilters(prev => ({ ...prev, status: value }))}
            allowClear
          >
            <Option value="active">已启用</Option>
            <Option value="inactive">已禁用</Option>
          </Select>
        </Space>
      </Card>

      {/* 用户列表 */}
      <Card>
        <Table
          columns={columns}
          dataSource={users}
          rowKey="id"
          loading={loading}
          pagination={{
            ...pagination,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (page, pageSize) => setPagination(prev => ({ ...prev, current: page, pageSize })),
          }}
          scroll={{ x: 1100 }}
        />
      </Card>

      {/* 编辑用户信息弹窗 */}
      <Modal
        title="编辑用户信息"
        open={editModalVisible}
        onCancel={() => setEditModalVisible(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleEditSubmit}>
          <Form.Item label="用户名" name="username">
            <Input disabled />
          </Form.Item>
          <Form.Item label="真实姓名" name="real_name" rules={[{ required: true, message: '请输入真实姓名' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="邮箱" name="email" rules={[{ type: 'email', message: '请输入有效邮箱' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="手机号" name="phone">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      {/* 修改角色弹窗 */}
      <Modal
        title="修改用户角色"
        open={roleModalVisible}
        onCancel={() => setRoleModalVisible(false)}
        onOk={() => roleForm.submit()}
      >
        <Form form={roleForm} layout="vertical" onFinish={handleRoleSubmit}>
          <Form.Item label="角色" name="role" rules={[{ required: true, message: '请选择角色' }]}>
            <Select>
              <Option value="admin">管理员</Option>
              <Option value="editor">编辑员</Option>
              <Option value="viewer">访客</Option>
              <Option value="uploader">上传员</Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Users;
