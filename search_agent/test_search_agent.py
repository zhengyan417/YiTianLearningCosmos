#!/usr/bin/env python3
"""
Search Agent 测试脚本
用于测试Search Agent的各项功能
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from search_agent.agent import SearchAgent

async def test_search_agent():
    """测试Search Agent功能"""
    print("=== Search Agent 功能测试 ===\n")
    
    # 创建SearchAgent实例
    agent = SearchAgent()
    
    # 测试用例
    test_cases = [
        {
            "name": "百度搜索测试",
            "query": "人工智能发展现状",
            "description": "测试网络搜索功能"
        },
        {
            "name": "用户信息查询测试",
            "query": "查询用户张三的信息",
            "description": "测试用户个人信息查询功能"
        },
        {
            "name": "用户历史查询测试", 
            "query": "查看张三的查询历史",
            "description": "测试用户历史记录查询功能"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"{i}. {test_case['name']}")
        print(f"   描述: {test_case['description']}")
        print(f"   查询: {test_case['query']}")
        print("   结果:")
        
        try:
            # 模拟context_id
            context_id = f"test_{i}"
            
            # 执行查询
            async for result in agent.stream(test_case['query'], context_id):
                if result['is_task_complete']:
                    print(f"     ✓ 完成: {result['content']}")
                elif result['require_user_input']:
                    print(f"     ⚠ 需要输入: {result['content']}")
                else:
                    print(f"     ... {result['content']}")
                    
        except Exception as e:
            print(f"     ✗ 错误: {str(e)}")
        
        print()

async def test_mcp_server_connection():
    """测试MCP服务器连接"""
    print("=== MCP服务器连接测试 ===\n")
    
    try:
        # 测试数据库连接
        from search_agent.mcp_server import get_db_connection
        conn = get_db_connection()
        print("✓ 数据库连接成功")
        conn.close()
        
        # 测试工具函数
        from search_agent.mcp_server import query_user_history, get_user_profile, baidu_search
        
        # 测试用户历史查询
        history_result = query_user_history("张三", 3)
        print(f"✓ 用户历史查询测试通过: {history_result[:100]}...")
        
        # 测试用户信息查询
        profile_result = get_user_profile("张三")
        print(f"✓ 用户信息查询测试通过: {profile_result[:100]}...")
        
        # 测试百度搜索
        search_result = baidu_search("人工智能", 3)
        print(f"✓ 百度搜索测试通过: {search_result[:100]}...")
        
    except Exception as e:
        print(f"✗ MCP服务器测试失败: {str(e)}")

def main():
    """主函数"""
    print("开始测试Search Agent...\n")
    
    # 运行测试
    asyncio.run(test_mcp_server_connection())
    print()
    asyncio.run(test_search_agent())
    
    print("测试完成!")

if __name__ == "__main__":
    main()