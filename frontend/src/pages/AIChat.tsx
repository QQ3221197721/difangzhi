import { useState, useRef, useEffect, useCallback } from 'react';
import { Card, Input, Button, Typography, Space, Avatar, Spin, List, Divider, Tooltip, message, Modal } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, PlusOutlined, HistoryOutlined, CopyOutlined } from '@ant-design/icons';
import { aiApi } from '../services/api';
import { useAuthStore } from '../stores/authStore';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: Date;
}

interface ChatSession {
  session_id: string;
  title: string;
  created_at: string;
}

const AIChat = () => {
  const { user } = useAuthStore();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionsVisible, setSessionsVisible] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<any>(null);

  // 滚动到底部
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // 加载历史会话
  const loadSessions = async () => {
    setLoadingSessions(true);
    try {
      const response = await aiApi.getChatSessions();
      setSessions(response.data || []);
    } catch (error) {
      console.error('Failed to load sessions:', error);
    } finally {
      setLoadingSessions(false);
    }
  };

  // 加载会话历史
  const loadSessionHistory = async (sid: string) => {
    setLoading(true);
    try {
      const response = await aiApi.getChatHistory(sid);
      const history = response.data?.messages || [];
      setMessages(history.map((m: any) => ({
        role: m.role,
        content: m.content,
        timestamp: new Date(m.created_at),
      })));
      setSessionId(sid);
      setSessionsVisible(false);
    } catch (error) {
      message.error('加载历史失败');
    } finally {
      setLoading(false);
    }
  };

  // 新建会话
  const handleNewChat = () => {
    setMessages([]);
    setSessionId(null);
    setInput('');
    inputRef.current?.focus();
  };

  // 发送消息
  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage, timestamp: new Date() }]);
    setLoading(true);

    try {
      const response = await aiApi.chat({ content: userMessage, session_id: sessionId });
      setSessionId(response.data.session_id);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.data.content,
        timestamp: new Date(),
      }]);
    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '抱歉，发生了错误，请稍后重试。',
        timestamp: new Date(),
      }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  // 复制消息
  const handleCopy = (content: string) => {
    navigator.clipboard.writeText(content);
    message.success('已复制到剪贴板');
  };

  // 快捷问题
  const quickQuestions = [
    '查找关于上海地区的历史资料',
    '近十年地方志记录的重大事件',
    '帮我总结一下经济发展趋势',
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 200px)' }}>
      {/* 头部 */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>AI 助手</Title>
          <Text type="secondary">智能问答，帮您解读地方志资料</Text>
        </div>
        <Space>
          <Button icon={<HistoryOutlined />} onClick={() => { setSessionsVisible(true); loadSessions(); }}>
            历史会话
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleNewChat}>
            新建对话
          </Button>
        </Space>
      </div>

      {/* 消息区域 */}
      <Card
        bodyStyle={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          padding: 0,
          overflow: 'hidden',
        }}
        style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
      >
        <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
          {messages.length === 0 ? (
            <div style={{ textAlign: 'center', marginTop: 60 }}>
              <RobotOutlined style={{ fontSize: 64, color: '#1677ff', marginBottom: 24 }} />
              <Title level={4}>您好！我是地方志AI助手</Title>
              <Paragraph type="secondary">
                我可以帮您查询地方志资料、总结分析数据、解答相关问题
              </Paragraph>
              <Divider>快捷问题</Divider>
              <Space wrap>
                {quickQuestions.map((q, i) => (
                  <Button
                    key={i}
                    onClick={() => { setInput(q); inputRef.current?.focus(); }}
                  >
                    {q}
                  </Button>
                ))}
              </Space>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  marginBottom: 24,
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                }}
              >
                {msg.role === 'assistant' && (
                  <Avatar icon={<RobotOutlined />} style={{ marginRight: 12, backgroundColor: '#1677ff', flexShrink: 0 }} />
                )}
                <div style={{ maxWidth: '75%' }}>
                  <div
                    style={{
                      padding: '12px 16px',
                      borderRadius: 12,
                      background: msg.role === 'user' ? '#1677ff' : '#f5f5f5',
                      color: msg.role === 'user' ? '#fff' : '#000',
                    }}
                  >
                    <Paragraph
                      style={{ margin: 0, whiteSpace: 'pre-wrap', color: 'inherit' }}
                    >
                      {msg.content}
                    </Paragraph>
                  </div>
                  <div style={{ marginTop: 4, display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                    <Space size="small">
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {msg.timestamp?.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                      </Text>
                      {msg.role === 'assistant' && (
                        <Tooltip title="复制">
                          <Button type="text" size="small" icon={<CopyOutlined />} onClick={() => handleCopy(msg.content)} />
                        </Tooltip>
                      )}
                    </Space>
                  </div>
                </div>
                {msg.role === 'user' && (
                  <Avatar
                    icon={<UserOutlined />}
                    src={user?.avatar_url}
                    style={{ marginLeft: 12, flexShrink: 0 }}
                  />
                )}
              </div>
            ))
          )}
          {loading && (
            <div style={{ display: 'flex', marginBottom: 24 }}>
              <Avatar icon={<RobotOutlined />} style={{ marginRight: 12, backgroundColor: '#1677ff' }} />
              <div style={{ padding: '12px 16px', borderRadius: 12, background: '#f5f5f5' }}>
                <Spin size="small" /> <Text type="secondary">正在思考...</Text>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* 输入区域 */}
        <div style={{ padding: 16, borderTop: '1px solid #f0f0f0', background: '#fafafa' }}>
          <Space.Compact style={{ width: '100%' }}>
            <TextArea
              ref={inputRef}
              placeholder="输入您的问题... (Enter发送, Shift+Enter换行)"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              disabled={loading}
              autoSize={{ minRows: 1, maxRows: 4 }}
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

      {/* 历史会话弹窗 */}
      <Modal
        title="历史会话"
        open={sessionsVisible}
        onCancel={() => setSessionsVisible(false)}
        footer={null}
        width={500}
      >
        <List
          loading={loadingSessions}
          dataSource={sessions}
          locale={{ emptyText: '暂无历史会话' }}
          renderItem={(session) => (
            <List.Item
              actions={[
                <Button type="link" onClick={() => loadSessionHistory(session.session_id)}>
                  加载
                </Button>,
              ]}
            >
              <List.Item.Meta
                title={session.title || '未命名会话'}
                description={new Date(session.created_at).toLocaleString('zh-CN')}
              />
            </List.Item>
          )}
        />
      </Modal>
    </div>
  );
};

export default AIChat;
