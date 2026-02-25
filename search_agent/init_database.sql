-- 创建用户档案表
CREATE TABLE IF NOT EXISTS user_profiles (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    education_level VARCHAR(50),
    major VARCHAR(100),
    university VARCHAR(200),
    graduation_year INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建用户查询历史表
CREATE TABLE IF NOT EXISTS user_queries (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    query_text TEXT NOT NULL,
    query_type VARCHAR(50) DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_user_profiles_username ON user_profiles(username);
CREATE INDEX IF NOT EXISTS idx_user_queries_username ON user_queries(username);
CREATE INDEX IF NOT EXISTS idx_user_queries_created_at ON user_queries(created_at);

-- 插入一些示例数据
INSERT INTO user_profiles (username, education_level, major, university, graduation_year) VALUES
('张三', '本科', '计算机科学与技术', '清华大学', 2023),
('李四', '硕士', '人工智能', '北京大学', 2024),
('王五', '博士', '数据科学', '浙江大学', 2025)
ON CONFLICT (username) DO NOTHING;

INSERT INTO user_queries (username, query_text, query_type) VALUES
('张三', 'Python编程教程', 'technical'),
('李四', '机器学习算法', 'academic'),
('王五', '大数据处理框架', 'research')
ON CONFLICT DO NOTHING;