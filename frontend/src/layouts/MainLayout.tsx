import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Avatar, Dropdown, Space, Typography } from 'antd';
import {
  DashboardOutlined,
  FileTextOutlined,
  UploadOutlined,
  SearchOutlined,
  BarChartOutlined,
  RobotOutlined,
  TagsOutlined,
  UserOutlined,
  LogoutOutlined,
  SettingOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons';
import { useAuthStore } from '../stores/authStore';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const menuItems = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '数据概览' },
  { key: '/documents', icon: <FileTextOutlined />, label: '文档管理' },
  { key: '/upload', icon: <UploadOutlined />, label: '数据上传' },
  { key: '/search', icon: <SearchOutlined />, label: '智能搜索' },
  { key: '/analytics', icon: <BarChartOutlined />, label: '数据分析' },
  { key: '/ai-chat', icon: <RobotOutlined />, label: 'AI 助手' },
  { key: '/categories', icon: <TagsOutlined />, label: '分类管理' },
  { key: '/users', icon: <UserOutlined />, label: '用户管理' },
];

const MainLayout = () => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();

  const handleMenuClick = (e: { key: string }) => {
    navigate(e.key);
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const userMenuItems = [
    {
      key: 'profile',
      icon: <SettingOutlined />,
      label: '个人设置',
      onClick: () => navigate('/profile'),
    },
    { type: 'divider' as const },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider 
        trigger={null} 
        collapsible 
        collapsed={collapsed}
        width={220}
      >
        <div style={{ 
          height: 64, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          borderBottom: '1px solid rgba(255,255,255,0.1)'
        }}>
          <Text style={{ 
            color: '#fff', 
            fontSize: collapsed ? 14 : 16, 
            fontWeight: 600 
          }}>
            {collapsed ? '地方志' : '地方志数据管理系统'}
          </Text>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={handleMenuClick}
        />
      </Sider>
      
      <Layout>
        <Header style={{ 
          padding: '0 24px', 
          background: '#fff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          boxShadow: '0 1px 4px rgba(0,21,41,.08)'
        }}>
          <Space>
            {collapsed ? (
              <MenuUnfoldOutlined 
                onClick={() => setCollapsed(false)} 
                style={{ fontSize: 18, cursor: 'pointer' }}
              />
            ) : (
              <MenuFoldOutlined 
                onClick={() => setCollapsed(true)} 
                style={{ fontSize: 18, cursor: 'pointer' }}
              />
            )}
          </Space>
          
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <Space style={{ cursor: 'pointer' }}>
              <Avatar 
                src={user?.avatar_url} 
                icon={<UserOutlined />}
                style={{ backgroundColor: '#1677ff' }}
              />
              <Text>{user?.real_name || user?.username}</Text>
            </Space>
          </Dropdown>
        </Header>
        
        <Content style={{ 
          margin: 24, 
          padding: 24, 
          background: '#fff',
          borderRadius: 8,
          minHeight: 'calc(100vh - 112px)'
        }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
