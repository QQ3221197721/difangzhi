import { Typography, Card, Tree, Button, Modal, Form, Input, Select, message, Space, Popconfirm, Table, Tag, InputNumber, Tabs, Tooltip } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons';
import { useEffect, useState, useCallback } from 'react';
import { categoryApi } from '../services/api';
import type { Category } from '../types';

const { Title } = Typography;
const { Option } = Select;

const categoryTypeLabels: Record<string, string> = {
  region: '地区',
  year: '年份',
  person: '人物',
  event: '事件',
};

const categoryTypeColors: Record<string, string> = {
  region: 'blue',
  year: 'green',
  person: 'orange',
  event: 'purple',
};

const Categories = () => {
  const [loading, setLoading] = useState(false);
  const [categories, setCategories] = useState<Category[]>([]);
  const [treeData, setTreeData] = useState<any[]>([]);
  const [modalVisible, setModalVisible] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [currentCategory, setCurrentCategory] = useState<Category | null>(null);
  const [activeTab, setActiveTab] = useState<string>('tree');
  const [selectedType, setSelectedType] = useState<string>('region');
  const [form] = Form.useForm();

  const fetchCategories = useCallback(async () => {
    setLoading(true);
    try {
      const [treeRes, listRes] = await Promise.all([
        categoryApi.tree(),
        categoryApi.list(),
      ]);
      
      // 树形数据
      const tree = treeRes.data.map((c: Category) => ({
        key: c.id,
        title: renderTreeTitle(c),
        data: c,
        children: c.children?.map((ch: Category) => ({
          key: ch.id,
          title: renderTreeTitle(ch),
          data: ch,
        })),
      }));
      setTreeData(tree);
      setCategories(listRes.data || []);
    } catch (error) {
      message.error('加载分类失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  // 渲染树节点标题
  const renderTreeTitle = (category: Category) => (
    <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span>{category.name}</span>
      <Tag color={categoryTypeColors[category.category_type]} style={{ marginRight: 0 }}>
        {categoryTypeLabels[category.category_type]}
      </Tag>
      <span style={{ color: '#999', fontSize: 12 }}>({category.code})</span>
    </span>
  );

  // 打开新建弹窗
  const handleCreate = (parentId?: number) => {
    setEditMode(false);
    setCurrentCategory(null);
    form.resetFields();
    if (parentId) {
      form.setFieldsValue({ parent_id: parentId });
    }
    setModalVisible(true);
  };

  // 打开编辑弹窗
  const handleEdit = (category: Category) => {
    setEditMode(true);
    setCurrentCategory(category);
    form.setFieldsValue(category);
    setModalVisible(true);
  };

  // 删除分类
  const handleDelete = async (id: number) => {
    try {
      await categoryApi.delete(id);
      message.success('删除成功');
      fetchCategories();
    } catch (error) {
      message.error('删除失败');
    }
  };

  // 提交表单
  const handleSubmit = async (values: any) => {
    try {
      if (editMode && currentCategory) {
        await categoryApi.update(currentCategory.id, values);
        message.success('修改成功');
      } else {
        await categoryApi.create(values);
        message.success('创建成功');
      }
      setModalVisible(false);
      form.resetFields();
      fetchCategories();
    } catch (error) {
      message.error(editMode ? '修改失败' : '创建失败');
    }
  };

  // 表格列
  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '名称', dataIndex: 'name', width: 150 },
    { title: '代码', dataIndex: 'code', width: 100 },
    {
      title: '类型',
      dataIndex: 'category_type',
      width: 100,
      render: (type: string) => (
        <Tag color={categoryTypeColors[type]}>{categoryTypeLabels[type]}</Tag>
      ),
    },
    { title: '层级', dataIndex: 'level', width: 80 },
    { title: '排序', dataIndex: 'sort_order', width: 80 },
    {
      title: '状态',
      dataIndex: 'is_active',
      width: 80,
      render: (active: boolean) => (
        <Tag color={active ? 'green' : 'default'}>{active ? '启用' : '禁用'}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: any, record: Category) => (
        <Space size="small">
          <Tooltip title="编辑">
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
          </Tooltip>
          <Popconfirm
            title="确认删除"
            description="确定要删除这个分类吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Tooltip title="删除">
              <Button type="text" size="small" danger icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // 按类型过滤
  const filteredCategories = categories.filter(c => c.category_type === selectedType);

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>分类管理</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchCategories}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => handleCreate()}>新建分类</Button>
        </Space>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'tree',
            label: '树形视图',
            children: (
              <Card loading={loading}>
                {treeData.length > 0 ? (
                  <Tree
                    treeData={treeData}
                    defaultExpandAll
                    showLine={{ showLeafIcon: false }}
                    blockNode
                    titleRender={(node: any) => (
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                        <span>{node.title}</span>
                        <Space size="small">
                          <Button type="link" size="small" onClick={(e) => { e.stopPropagation(); handleEdit(node.data); }}>编辑</Button>
                          {node.data.level < 2 && (
                            <Button type="link" size="small" onClick={(e) => { e.stopPropagation(); handleCreate(node.data.id); }}>添加子分类</Button>
                          )}
                          <Popconfirm
                            title="确认删除"
                            description="确定要删除这个分类吗？"
                            onConfirm={(e) => { e?.stopPropagation(); handleDelete(node.data.id); }}
                            okText="确定"
                            cancelText="取消"
                          >
                            <Button type="link" size="small" danger onClick={(e) => e.stopPropagation()}>删除</Button>
                          </Popconfirm>
                        </Space>
                      </div>
                    )}
                  />
                ) : (
                  <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>暂无分类数据</div>
                )}
              </Card>
            ),
          },
          {
            key: 'table',
            label: '列表视图',
            children: (
              <Card>
                <Space style={{ marginBottom: 16 }}>
                  <span>分类类型：</span>
                  <Select value={selectedType} onChange={setSelectedType} style={{ width: 120 }}>
                    <Option value="region">地区</Option>
                    <Option value="year">年份</Option>
                    <Option value="person">人物</Option>
                    <Option value="event">事件</Option>
                  </Select>
                </Space>
                <Table
                  columns={columns}
                  dataSource={filteredCategories}
                  rowKey="id"
                  loading={loading}
                  pagination={{ showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
                />
              </Card>
            ),
          },
        ]}
      />

      {/* 新建/编辑弹窗 */}
      <Modal
        title={editMode ? '编辑分类' : '新建分类'}
        open={modalVisible}
        onCancel={() => { setModalVisible(false); form.resetFields(); }}
        onOk={() => form.submit()}
        width={480}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入分类名称' }]}>
            <Input placeholder="请输入分类名称" />
          </Form.Item>
          <Form.Item label="代码" name="code" rules={[{ required: true, message: '请输入分类代码' }]}>
            <Input placeholder="如: region_shanghai, year_2024" />
          </Form.Item>
          <Form.Item label="类型" name="category_type" rules={[{ required: true, message: '请选择分类类型' }]}>
            <Select placeholder="请选择分类类型">
              <Option value="region">地区</Option>
              <Option value="year">年份</Option>
              <Option value="person">人物</Option>
              <Option value="event">事件</Option>
            </Select>
          </Form.Item>
          <Form.Item label="父级分类" name="parent_id">
            <Select placeholder="选择父级分类（可选）" allowClear>
              {categories.filter(c => c.level === 0).map(c => (
                <Option key={c.id} value={c.id}>{c.name}</Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item label="排序" name="sort_order" initialValue={0}>
            <InputNumber min={0} max={9999} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={3} placeholder="分类描述（可选）" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Categories;
