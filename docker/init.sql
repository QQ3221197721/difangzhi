-- =====================================================
-- 地方志数据智能管理系统 - PostgreSQL 初始化脚本
-- 支持中文全文搜索、模糊匹配、高性能索引
-- =====================================================

-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";  -- 向量搜索扩展

-- =====================================================
-- 用户表
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    real_name VARCHAR(50) NOT NULL,
    id_card VARCHAR(18),
    phone VARCHAR(20),
    role VARCHAR(20) DEFAULT 'viewer',
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    avatar_url VARCHAR(500),
    last_login TIMESTAMP,
    last_location JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 登录日志表
-- =====================================================
CREATE TABLE IF NOT EXISTS login_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    ip_address VARCHAR(50),
    user_agent VARCHAR(500),
    location JSONB,
    latitude FLOAT,
    longitude FLOAT,
    login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_success BOOLEAN DEFAULT TRUE,
    fail_reason VARCHAR(200)
);

-- =====================================================
-- 分类表
-- =====================================================
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) UNIQUE,
    level INTEGER DEFAULT 1,
    parent_id INTEGER REFERENCES categories(id),
    category_type VARCHAR(50),
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 文档表
-- =====================================================
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content TEXT,
    full_text TEXT,
    source VARCHAR(200),
    author VARCHAR(100),
    publish_date TIMESTAMP,
    file_path VARCHAR(500),
    file_name VARCHAR(200),
    file_size INTEGER,
    file_type VARCHAR(50),
    region VARCHAR(100),
    year INTEGER,
    tags TEXT[],
    ai_summary TEXT,
    ai_keywords TEXT[],
    embedding FLOAT[],
    search_vector TSVECTOR,
    status VARCHAR(20) DEFAULT 'pending',
    upload_type VARCHAR(20) DEFAULT 'file',
    uploader_id INTEGER REFERENCES users(id),
    reviewer_id INTEGER REFERENCES users(id),
    review_comment TEXT,
    reviewed_at TIMESTAMP,
    view_count INTEGER DEFAULT 0,
    download_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 文档-分类关联表
-- =====================================================
CREATE TABLE IF NOT EXISTS document_categories (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES categories(id),
    UNIQUE(document_id, category_id)
);

-- =====================================================
-- AI 对话记录表
-- =====================================================
CREATE TABLE IF NOT EXISTS ai_chats (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    session_id VARCHAR(50),
    role VARCHAR(20),
    content TEXT,
    tokens_used INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 操作日志表
-- =====================================================
CREATE TABLE IF NOT EXISTS operation_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(50),
    resource_type VARCHAR(50),
    resource_id INTEGER,
    detail JSONB,
    ip_address VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 创建索引
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_users_real_name ON users(real_name);
CREATE INDEX IF NOT EXISTS idx_documents_region_year ON documents(region, year);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_search_vector ON documents USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_documents_title_trgm ON documents USING GIN(title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_categories_type_level ON categories(category_type, level);
CREATE INDEX IF NOT EXISTS idx_ai_chats_user_session ON ai_chats(user_id, session_id);
CREATE INDEX IF NOT EXISTS idx_operation_logs_user_action ON operation_logs(user_id, action);
CREATE INDEX IF NOT EXISTS idx_operation_logs_created_at ON operation_logs(created_at);

-- =====================================================
-- 全文搜索向量更新触发器
-- =====================================================
CREATE OR REPLACE FUNCTION update_document_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('simple', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('simple', COALESCE(NEW.region, '')), 'A') ||
        setweight(to_tsvector('simple', COALESCE(NEW.author, '')), 'B') ||
        setweight(to_tsvector('simple', COALESCE(NEW.content, '')), 'C') ||
        setweight(to_tsvector('simple', COALESCE(NEW.ai_summary, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_document_search_vector ON documents;
CREATE TRIGGER trigger_update_document_search_vector
    BEFORE INSERT OR UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_document_search_vector();

-- =====================================================
-- 初始化分类数据
-- =====================================================
INSERT INTO categories (name, code, level, category_type, description, sort_order, is_active)
VALUES 
    ('地区', 'region', 1, 'region', '按行政区域分类', 1, true),
    ('年份', 'year', 1, 'year', '按年份分类', 2, true),
    ('人物', 'person', 1, 'person', '按相关人物分类', 3, true),
    ('事件', 'event', 1, 'event', '按历史事件分类', 4, true),
    ('其他', 'other', 1, 'other', '其他分类', 5, true)
ON CONFLICT (code) DO NOTHING;

-- =====================================================
-- 初始化年份二级分类 (2000-2050)
-- =====================================================
DO $$
DECLARE
    parent_id INTEGER;
    year_val INTEGER;
BEGIN
    SELECT id INTO parent_id FROM categories WHERE code = 'year' LIMIT 1;
    IF parent_id IS NOT NULL THEN
        FOR year_val IN 2000..2050 LOOP
            INSERT INTO categories (name, code, level, parent_id, category_type, sort_order, is_active)
            VALUES (year_val::TEXT, 'year_' || year_val, 2, parent_id, 'year', year_val - 1999, true)
            ON CONFLICT (code) DO NOTHING;
        END LOOP;
    END IF;
END $$;

-- =====================================================
-- 创建管理员账户（密码: Admin@123456）
-- =====================================================
INSERT INTO users (username, email, hashed_password, real_name, is_verified, is_active, role)
VALUES (
    'admin',
    'admin@example.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4bSUgVBJsS0V7dHe',
    '系统管理员',
    true,
    true,
    'admin'
) ON CONFLICT (username) DO NOTHING;

-- =====================================================
-- 表注释
-- =====================================================
COMMENT ON TABLE users IS '用户表 - 存储用户基本信息和认证数据';
COMMENT ON TABLE documents IS '文档表 - 地方志数据核心存储';
COMMENT ON TABLE categories IS '分类表 - 支持两级分类体系';
COMMENT ON TABLE ai_chats IS 'AI对话记录表 - 存储用户与AI的对话历史';
COMMENT ON TABLE operation_logs IS '操作日志表 - 记录用户操作审计';

-- =====================================================
-- 完成
-- =====================================================
SELECT '数据库初始化完成!' AS message;
