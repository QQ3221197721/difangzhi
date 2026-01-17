import React, { useState, useEffect, useRef } from 'react';
import {
  Card, Input, Button, List, Avatar, Typography, Space, Spin,
  Row, Col, Tag, Drawer, Empty, message, Divider
} from 'antd';
import {
  RobotOutlined, UserOutlined, SendOutlined,
  HistoryOutlined, DeleteOutlined, PlusOutlined,
  BulbOutlined
} from '@ant-design/icons';
import { aiService } from '../services/api';

const { Text, Paragraph, Title } = Typography;
const { TextArea } = Input;

const AIAssistant = () => {
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [historyVisible, setHistoryVisible] = useState(false);
  const messagesEndRef = useRef(null);

  // 示例问题
  const exampleQuestions = [
    '帮我查询辽宁省2023年的工业数据',
    '分析葫芦岛市近五年的经济发展趋势',
    '哪些地区的农业收入最高？',
    '如何使用数据分析功能？',
    '生成一份2022年全省数据汇总报告',
  ];

  useEffect(() => {
    fetchSessions();
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const fetchSessions = async () => {
    try {
      const response = await aiService.getSessions();
      setSessions(response.data.sessions);
    } catch (error) {
      console.error('获取会话列表失败:', error);
    }
  };

  const loadSession = async (sid) => {
    try {
      const response = await aiService.getSessionHistory(sid);
      setMessages(response.data.messages.map((m, i) => ({
        id: i,
        role: m.role,
        content: m.content,
        time: m.created_at,
      })));
      setSessionId(sid);
      setHistoryVisible(false);
    } catch (error) {
      message.error('加载会话失败');
    }
  };

  const deleteSession = async (sid) => {
    try {
      await aiService.deleteSession(sid);
      message.success('会话已删除');
      fetchSessions();
      if (sessionId === sid) {
        setMessages([]);
        setSessionId(null);
      }
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleSend = async () => {
    if (!inputValue.trim()) return;

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: inputValue,
      time: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setLoading(true);

    try {
      const response = await aiService.chat(inputValue, sessionId);
      const { session_id, message: aiMessage, suggestions, related_records } = response.data;

      setSessionId(session_id);

      const assistantMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: aiMessage,
        suggestions,
        related_records,
        time: new Date().toISOString(),
      };

      setMessages(prev => [...prev, assistantMessage]);
      fetchSessions();
    } catch (error) {
      message.error('发送失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleExampleClick = (question) => {
    setInputValue(question);
  };

  const startNewChat = () => {
    setMessages([]);
    setSessionId(null);
  };

  // 消息气泡组件
  const MessageBubble = ({ msg }) => {
    const isUser = msg.role === 'user';

    return (
      <div style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: 16,
      }}>
        <div style={{
          display: 'flex',
          flexDirection: isUser ? 'row-reverse' : 'row',
          alignItems: 'flex-start',
          maxWidth: '80%',
        }}>
          <Avatar
            icon={isUser ? <UserOutlined /> : <RobotOutlined />}
            style={{
              backgroundColor: isUser ? '#1890ff' : '#52c41a',
              margin: isUser ? '0 0 0 12px' : '0 12px 0 0',
            }}
          />
          <div>
            <div style={{
              background: isUser ? '#1890ff' : '#f0f2f5',
              color: isUser ? '#fff' : '#000',
              padding: '12px 16px',
              borderRadius: isUser ? '12px 12px 0 12px' : '12px 12px 12px 0',
            }}>
              <Paragraph style={{ margin: 0, color: 'inherit', whiteSpace: 'pre-wrap' }}>
                {msg.content}
              </Paragraph>
            </div>

            {/* 建议 */}
            {msg.suggestions && msg.suggestions.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>建议：</Text>
                <div>
                  {msg.suggestions.map((s, i) => (
                    <Tag key={i} color="blue" style={{ margin: '4px 4px 0 0' }}>{s}</Tag>
                  ))}
                </div>
              </div>
            )}

            {/* 相关记录 */}
            {msg.related_records && msg.related_records.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>相关数据：</Text>
                <div>
                  {msg.related_records.slice(0, 3).map((r, i) => (
                    <Tag key={i} style={{ margin: '4px 4px 0 0' }}>{r.title}</Tag>
                  ))}
                </div>
              </div>
            )}

            <Text type="secondary" style={{ fontSize: 12, marginTop: 4, display: 'block' }}>
              {new Date(msg.time).toLocaleTimeString()}
            </Text>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div>
      <Title level={4}>AI助手</Title>
      <Text type="secondary" style={{ marginBottom: 24, display: 'block' }}>
        智能对话助手，支持数据查询、分析建议和报告生成
      </Text>

      <Row gutter={16}>
        {/* 聊天区域 */}
        <Col xs={24} lg={18}>
          <Card
            title={
              <Space>
                <RobotOutlined />
                <span>AI对话</span>
                {sessionId && <Tag color="blue">会话中</Tag>}
              </Space>
            }
            extra={
              <Space>
                <Button icon={<PlusOutlined />} onClick={startNewChat}>新对话</Button>
                <Button icon={<HistoryOutlined />} onClick={() => setHistoryVisible(true)}>历史</Button>
              </Space>
            }
            bodyStyle={{ padding: 0 }}
          >
            {/* 消息列表 */}
            <div style={{
              height: 500,
              overflow: 'auto',
              padding: 16,
              background: '#fafafa',
            }}>
              {messages.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '60px 0' }}>
                  <RobotOutlined style={{ fontSize: 48, color: '#bfbfbf' }} />
                  <Title level={5} type="secondary">你好！我是AI助手</Title>
                  <Paragraph type="secondary">
                    我可以帮你查询数据、分析趋势、生成报告，请随时提问！
                  </Paragraph>
                </div>
              ) : (
                messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)
              )}
              {loading && (
                <div style={{ textAlign: 'center', padding: 16 }}>
                  <Spin tip="AI正在思考..." />
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* 输入区域 */}
            <div style={{ padding: 16, borderTop: '1px solid #f0f0f0' }}>
              <Space.Compact style={{ width: '100%' }}>
                <TextArea
                  value={inputValue}
                  onChange={e => setInputValue(e.target.value)}
                  placeholder="输入你的问题..."
                  autoSize={{ minRows: 1, maxRows: 4 }}
                  onPressEnter={e => {
                    if (!e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  style={{ borderRadius: '8px 0 0 8px' }}
                />
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  onClick={handleSend}
                  loading={loading}
                  style={{ height: 'auto', borderRadius: '0 8px 8px 0' }}
                >
                  发送
                </Button>
              </Space.Compact>
            </div>
          </Card>
        </Col>

        {/* 快捷提问 */}
        <Col xs={24} lg={6}>
          <Card title={<><BulbOutlined /> 快捷提问</>}>
            <List
              size="small"
              dataSource={exampleQuestions}
              renderItem={item => (
                <List.Item
                  style={{ cursor: 'pointer', padding: '8px 0' }}
                  onClick={() => handleExampleClick(item)}
                >
                  <Text ellipsis style={{ width: '100%' }}>{item}</Text>
                </List.Item>
              )}
            />
          </Card>

          <Card title="使用技巧" style={{ marginTop: 16 }}>
            <List size="small">
              <List.Item>输入自然语言即可查询数据</List.Item>
              <List.Item>可以要求生成分析报告</List.Item>
              <List.Item>支持多轮对话上下文</List.Item>
              <List.Item>Shift+Enter 换行</List.Item>
            </List>
          </Card>
        </Col>
      </Row>

      {/* 历史会话抽屉 */}
      <Drawer
        title="历史会话"
        placement="right"
        width={360}
        open={historyVisible}
        onClose={() => setHistoryVisible(false)}
      >
        {sessions.length === 0 ? (
          <Empty description="暂无历史会话" />
        ) : (
          <List
            dataSource={sessions}
            renderItem={session => (
              <List.Item
                actions={[
                  <Button
                    type="text"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => deleteSession(session.session_id)}
                  />,
                ]}
              >
                <List.Item.Meta
                  avatar={<Avatar icon={<RobotOutlined />} />}
                  title={
                    <a onClick={() => loadSession(session.session_id)}>
                      会话 {session.session_id.slice(0, 8)}...
                    </a>
                  }
                  description={new Date(session.created_at).toLocaleString()}
                />
              </List.Item>
            )}
          />
        )}
      </Drawer>
    </div>
  );
};

export default AIAssistant;
