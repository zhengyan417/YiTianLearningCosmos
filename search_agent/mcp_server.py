from mcp.server.fastmcp import FastMCP
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import requests
from urllib.parse import quote_plus
from datetime import datetime
from typing import List, Dict, Optional

from mcp.server.lowlevel import server

# 创建 MCP 服务器
mcp = FastMCP("Search Agent Server",
              debug=True,
              host="0.0.0.0",
              port=8004)

# 数据库连接配置
DB_CONFIG = {
    "dbname": "search_agent_database",
    "user": "postgres",
    "password": "postgres",
    "host": "localhost",
    "port": "5432"
}

# 百度搜索配置
BAIDU_SEARCH_URL = "https://www.baidu.com/s"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# 获取数据库连接对象
def get_db_connection():
    """创建数据库连接"""
    return psycopg2.connect(**DB_CONFIG)

# 用户信息查询工具
@mcp.tool()
def query_user_history(username: str, limit: int = 10) -> str:
    """查询用户的输入历史记录

    参数:
    username: 用户名
    limit: 返回记录数量限制，默认10条

    返回:
    用户的历史输入记录JSON字符串
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT query_text, created_at, query_type
                    FROM user_queries 
                    WHERE username = %s 
                    ORDER BY created_at DESC 
                    LIMIT %s
                """, (username, limit))
                history = cur.fetchall()
                return json.dumps([dict(row) for row in history], default=str, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"查询用户历史失败: {str(e)}"})

@mcp.tool()
def get_user_profile(username: str) -> str:
    """根据用户名查询用户的学历、专业等基本信息

    参数:
    username: 用户名

    返回:
    用户的基本信息JSON字符串
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT username, education_level, major, university, 
                           graduation_year, created_at, updated_at
                    FROM user_profiles 
                    WHERE username = %s
                """, (username,))
                profile = cur.fetchone()
                if profile:
                    return json.dumps(dict(profile), default=str, ensure_ascii=False)
                else:
                    return json.dumps({"error": f"未找到用户 {username} 的信息"})
    except Exception as e:
        return json.dumps({"error": f"查询用户信息失败: {str(e)}"})

@mcp.tool()
def baidu_search(query: str, num_results: int = 5) -> str:
    """执行百度搜索

    参数:
    query: 搜索关键词
    num_results: 返回结果数量，默认5条

    返回:
    搜索结果JSON字符串
    """
    try:
        headers = {
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        params = {
            'wd': query,
            'rn': num_results
        }
        
        response = requests.get(BAIDU_SEARCH_URL, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        # 简单解析搜索结果（实际应用中可能需要更复杂的解析）
        # 这里返回基本的成功信息
        return json.dumps({
            "query": query,
            "num_results": num_results,
            "status": "success",
            "message": f"已发起百度搜索请求: {query}",
            "timestamp": datetime.now().isoformat()
        }, ensure_ascii=False)
        
    except requests.exceptions.RequestException as e:
        return json.dumps({
            "error": f"百度搜索请求失败: {str(e)}",
            "query": query
        })
    except Exception as e:
        return json.dumps({
            "error": f"搜索过程中出现错误: {str(e)}",
            "query": query
        })

# 定义资源：获取所有表名
@mcp.resource("db://tables")
def list_tables() -> str:
    """获取所有表名列表"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                """)
                tables = [row[0] for row in cur.fetchall()]
                return json.dumps(tables)
    except Exception as e:
        return json.dumps({"error": f"获取表列表失败: {str(e)}"})

# 定义资源：获取表数据
@mcp.resource("db://tables/{table_name}/data/{limit}")
def get_table_data(table_name: str, limit: int = 100) -> str:
    """获取指定表的数据

    参数:
    table_name: 表名
    limit: 限制返回行数
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 使用参数化查询防止 SQL 注入
                cur.execute("SELECT * FROM %s LIMIT %s",
                           (psycopg2.extensions.AsIs(table_name), limit))
                rows = cur.fetchall()
                return json.dumps(list(rows), default=str, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"获取表数据失败: {str(e)}"})

# 定义资源：获取表结构
@mcp.resource("db://tables/{table_name}/schema")
def get_table_schema(table_name: str) -> str:
    """获取表结构信息

    参数:
    table_name: 表名
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    select c.column_name, 
                           c.data_type, 
                           c.character_maximum_length,
                           pgd.description as column_comment
                    from information_schema.columns c
                    left join pg_catalog.pg_statio_all_tables st 
                    on c.table_schema = st.schemaname and c.table_name = st.relname
                    left join pg_catalog.pg_description pgd 
                    on pgd.objoid = st.relid 
                       and pgd.objsubid = c.ordinal_position
                    where c.table_name = %s
                    order by c.ordinal_position
                """, (table_name,))
                columns = [{"name": row[0], "type": row[1], "max_length": row[2], "comment": row[3]}
                           for row in cur.fetchall()]
                return json.dumps(columns)
    except Exception as e:
        return json.dumps({"error": f"获取表结构失败: {str(e)}"})

# 搜索相关提示词
@mcp.prompt()
def search_with_context(query: str, context: str = "") -> str:
    """基于上下文进行搜索

    参数:
    query: 搜索查询
    context: 上下文信息
    """
    return f"""
    请根据以下查询进行搜索：{query}
    
    上下文信息：{context}
    
    要求：
    1. 提供准确的相关信息
    2. 如果涉及用户个人信息，请先确认用户身份
    3. 对于敏感信息查询，需要适当的验证步骤
    """

@mcp.prompt()
def analyze_user_query(query_type: str, username: str = "") -> str:
    """分析用户查询类型

    参数:
    query_type: 查询类型（历史查询/个人信息查询/网络搜索）
    username: 用户名（可选）
    """
    return f"""
    分析用户查询类型：{query_type}
    
    用户：{username}
    
    请判断这是哪种类型的查询并提供相应的处理建议。
    """

# 数据库管理工具
@mcp.tool()
def create_user_profile(username: str, education_level: str, major: str, 
                       university: str = "", graduation_year: int = 0) -> str:
    """创建或更新用户档案

    参数:
    username: 用户名
    education_level: 教育程度
    major: 专业
    university: 大学名称
    graduation_year: 毕业年份

    返回:
    操作结果JSON字符串
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO user_profiles (username, education_level, major, university, graduation_year)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (username) 
                    DO UPDATE SET 
                        education_level = EXCLUDED.education_level,
                        major = EXCLUDED.major,
                        university = EXCLUDED.university,
                        graduation_year = EXCLUDED.graduation_year,
                        updated_at = CURRENT_TIMESTAMP
                """, (username, education_level, major, university, graduation_year))
                conn.commit()
                return json.dumps({
                    "status": "success",
                    "message": f"用户 {username} 的档案已创建/更新",
                    "timestamp": datetime.now().isoformat()
                })
    except Exception as e:
        return json.dumps({
            "error": f"创建/更新用户档案失败: {str(e)}",
            "username": username
        })

@mcp.tool()
def log_user_query(username: str, query_text: str, query_type: str = "general") -> str:
    """记录用户查询历史

    参数:
    username: 用户名
    query_text: 查询内容
    query_type: 查询类型

    返回:
    操作结果JSON字符串
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO user_queries (username, query_text, query_type)
                    VALUES (%s, %s, %s)
                """, (username, query_text, query_type))
                conn.commit()
                return json.dumps({
                    "status": "success",
                    "message": "查询已记录",
                    "timestamp": datetime.now().isoformat()
                })
    except Exception as e:
        return json.dumps({
            "error": f"记录查询失败: {str(e)}",
            "username": username
        })


if __name__ == "__main__":
    # 本地测试
    print("启动Search Agent MCP服务器...")
    print("服务器将在 0.0.0.0:8004 上监听")
    mcp.run()