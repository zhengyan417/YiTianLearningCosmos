"""
依天学境项目综合功能测试
测试各个智能体的基本功能
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import setup_logging, get_logger
from file_parse_agent.agent import ParseAndChat
from rag_agent.agent import DoctorRAGWorkflow
from code_agent.agent import CodeAgent

# 配置日志
logger = setup_logging(log_level="INFO", console_output=True)


async def test_file_parse_agent():
    """测试文件解析智能体"""
    print("\n" + "="*50)
    print("测试文件解析智能体")
    print("="*50)
    
    try:
        # 创建智能体实例
        agent = ParseAndChat()
        logger.info("文件解析智能体创建成功")
        
        # 测试基本初始化
        print("✓ 智能体初始化成功")
        return True
        
    except Exception as e:
        logger.error(f"文件解析智能体测试失败: {e}")
        print(f"✗ 智能体初始化失败: {e}")
        return False


async def test_doctor_agent():
    """测试医生智能体"""
    print("\n" + "="*50)
    print("测试医生智能体")
    print("="*50)
    
    try:
        # 创建智能体实例
        agent = DoctorRAGWorkflow()
        logger.info("医生智能体创建成功")
        
        # 测试基本初始化
        print("✓ 智能体初始化成功")
        return True
        
    except Exception as e:
        logger.error(f"医生智能体测试失败: {e}")
        print(f"✗ 智能体初始化失败: {e}")
        return False


def test_code_agent():
    """测试代码智能体"""
    print("\n" + "="*50)
    print("测试代码智能体")
    print("="*50)
    
    try:
        # 创建智能体实例
        agent = CodeAgent()
        logger.info("代码智能体创建成功")
        
        # 测试基本初始化
        print("✓ 智能体初始化成功")
        return True
        
    except Exception as e:
        logger.error(f"代码智能体测试失败: {e}")
        print(f"✗ 智能体初始化失败: {e}")
        return False


async def test_env_variables():
    """测试环境变量配置"""
    print("\n" + "="*50)
    print("测试环境变量配置")
    print("="*50)
    
    required_vars = [
        'DASHSCOPE_API_KEY',
        'LLAMA_CLOUD_API_KEY',
        'DEEPSEEK_API_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✓ {var}: 已配置")
        else:
            print(f"✗ {var}: 未配置")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n警告: 缺少以下环境变量: {missing_vars}")
        print("某些功能可能无法正常工作")
        return False
    else:
        print("\n✓ 所有必需的环境变量都已配置")
        return True


async def run_comprehensive_tests():
    """运行综合测试"""
    print("🚀 开始依天学境项目综合测试")
    print("="*60)
    
    results = []
    
    # 测试环境变量
    env_result = await test_env_variables()
    results.append(("环境变量配置", env_result))
    
    # 测试各个智能体
    file_result = await test_file_parse_agent()
    results.append(("文件解析智能体", file_result))
    
    doctor_result = await test_doctor_agent()
    results.append(("医生智能体", doctor_result))
    
    code_result = test_code_agent()
    results.append(("代码智能体", code_result))
    
    # 输出测试总结
    print("\n" + "="*60)
    print("测试结果总结")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed} 个通过, {failed} 个失败")
    
    if failed == 0:
        print("🎉 所有测试都通过了！项目运行正常。")
    else:
        print("⚠️  部分测试失败，请检查上述错误信息。")
    
    return failed == 0


if __name__ == "__main__":
    try:
        success = asyncio.run(run_comprehensive_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)