-- 数据库初始化脚本
-- 创建扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- 用于模糊搜索

-- 创建全文搜索配置
CREATE TEXT SEARCH CONFIGURATION chinese (COPY = simple);

-- 创建索引函数（用于全文搜索）
CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('chinese', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('chinese', COALESCE(NEW.content, '')), 'B') ||
        setweight(to_tsvector('chinese', COALESCE(NEW.summary, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 初始分类数据
INSERT INTO categories (id, name, level, description, sort_order, is_active)
VALUES 
    (uuid_generate_v4(), '地区', 1, '按行政区域分类', 1, true),
    (uuid_generate_v4(), '年份', 1, '按年份分类', 2, true),
    (uuid_generate_v4(), '单位', 1, '按组织单位分类', 3, true),
    (uuid_generate_v4(), '人物', 1, '按相关人物分类', 4, true),
    (uuid_generate_v4(), '收入', 1, '按收入范围分类', 5, true),
    (uuid_generate_v4(), '工作类别', 1, '按行业类别分类', 6, true)
ON CONFLICT DO NOTHING;

-- 创建年份二级分类
DO $$
DECLARE
    parent_id UUID;
    year_val INT;
BEGIN
    SELECT id INTO parent_id FROM categories WHERE name = '年份' AND level = 1 LIMIT 1;
    IF parent_id IS NOT NULL THEN
        FOR year_val IN 2000..2050 LOOP
            INSERT INTO categories (id, name, level, parent_id, sort_order, is_active)
            VALUES (uuid_generate_v4(), year_val::TEXT, 2, parent_id, year_val - 1999, true)
            ON CONFLICT DO NOTHING;
        END LOOP;
    END IF;
END $$;

-- 创建工作类别二级分类
DO $$
DECLARE
    parent_id UUID;
    category_name TEXT;
    i INT := 1;
BEGIN
    SELECT id INTO parent_id FROM categories WHERE name = '工作类别' AND level = 1 LIMIT 1;
    IF parent_id IS NOT NULL THEN
        FOREACH category_name IN ARRAY ARRAY['农业', '工业', '服务业', '科技', '教育', '医疗', '金融', '交通', '建筑', '其他'] LOOP
            INSERT INTO categories (id, name, level, parent_id, sort_order, is_active)
            VALUES (uuid_generate_v4(), category_name, 2, parent_id, i, true)
            ON CONFLICT DO NOTHING;
            i := i + 1;
        END LOOP;
    END IF;
END $$;

-- 创建收入范围二级分类
DO $$
DECLARE
    parent_id UUID;
    range_name TEXT;
    i INT := 1;
BEGIN
    SELECT id INTO parent_id FROM categories WHERE name = '收入' AND level = 1 LIMIT 1;
    IF parent_id IS NOT NULL THEN
        FOREACH range_name IN ARRAY ARRAY['0-10万', '10-50万', '50-100万', '100-500万', '500万以上'] LOOP
            INSERT INTO categories (id, name, level, parent_id, sort_order, is_active)
            VALUES (uuid_generate_v4(), range_name, 2, parent_id, i, true)
            ON CONFLICT DO NOTHING;
            i := i + 1;
        END LOOP;
    END IF;
END $$;

-- 创建管理员账户（密码: Admin@123456）
INSERT INTO users (id, username, email, hashed_password, real_name, is_verified, status, role)
VALUES (
    uuid_generate_v4(),
    'admin',
    'admin@example.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4bSUgVBJsS0V7dHe',
    '系统管理员',
    true,
    'active',
    'admin'
) ON CONFLICT (username) DO NOTHING;

-- 授权说明
COMMENT ON TABLE users IS '用户表 - 存储用户基本信息和认证数据';
COMMENT ON TABLE chronicle_records IS '地方志数据记录表 - 核心数据存储';
COMMENT ON TABLE categories IS '分类标签表 - 支持两级分类体系';
COMMENT ON TABLE file_uploads IS '文件上传记录表 - 跟踪上传和处理状态';
