"""
错误处理和日志系统测试脚本
验证新添加的功能是否正常工作
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core import (
    handle_exceptions,
    retry_on_failure,
    with_logging_context,
    get_logger,
    setup_logging,
    FileParsingError,
    ModelCallError,
    EnvironmentError,
    InternalServerError
)


# 配置测试日志
logger = setup_logging(
    log_level="DEBUG",
    console_output=True,
    log_format="detailed"
)


class TestService:
    """测试服务类"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.call_count = 0
    
    @handle_exceptions
    @with_logging_context(service="test_service", version="1.0")
    def divide_numbers(self, a: float, b: float) -> float:
        """测试基本异常处理"""
        self.logger.info(f"执行除法运算: {a} / {b}")
        if b == 0:
            raise ValueError("除数不能为零")
        return a / b
    
    @handle_exceptions
    @retry_on_failure(max_retries=3, delay=0.1)
    def unreliable_operation(self) -> str:
        """测试重试机制"""
        self.call_count += 1
        self.logger.info(f"执行不稳定操作，第 {self.call_count} 次尝试")
        
        if self.call_count < 3:
            raise ConnectionError("模拟网络连接失败")
        
        self.logger.info("操作成功完成")
        return "success"
    
    @handle_exceptions
    async def async_operation(self, should_fail: bool = False) -> str:
        """测试异步异常处理"""
        self.logger.info("开始异步操作")
        await asyncio.sleep(0.1)
        
        if should_fail:
            raise RuntimeError("模拟异步操作失败")
        
        self.logger.info("异步操作完成")
        return "async_success"


async def run_tests():
    """运行所有测试"""
    print("=" * 50)
    print("开始错误处理和日志系统测试")
    print("=" * 50)
    
    service = TestService()
    
    # 测试1: 基本异常处理
    print("\n1. 测试基本异常处理:")
    try:
        result = service.divide_numbers(10, 2)
        print(f"✓ 正常情况: 10 / 2 = {result}")
    except Exception as e:
        print(f"✗ 正常情况失败: {e}")
    
    try:
        result = service.divide_numbers(10, 0)
        print(f"✗ 异常情况应该失败但没有: {result}")
    except ValueError as e:
        print(f"✓ 异常情况正确捕获: {e}")
    except Exception as e:
        print(f"✗ 意外异常: {e}")
    
    # 测试2: 重试机制
    print("\n2. 测试重试机制:")
    service.call_count = 0
    try:
        result = service.unreliable_operation()
        print(f"✓ 重试后成功: {result}")
        print(f"  总调用次数: {service.call_count}")
    except Exception as e:
        print(f"✗ 重试后仍然失败: {e}")
    
    # 测试3: 异步异常处理
    print("\n3. 测试异步异常处理:")
    try:
        result = await service.async_operation(False)
        print(f"✓ 异步操作成功: {result}")
    except Exception as e:
        print(f"✗ 异步操作失败: {e}")
    
    try:
        result = await service.async_operation(True)
        print(f"✗ 异步异常应该失败但没有: {result}")
    except RuntimeError as e:
        print(f"✓ 异步异常正确捕获: {e}")
    except Exception as e:
        print(f"✗ 异步意外异常: {e}")
    
    # 测试4: 自定义异常
    print("\n4. 测试自定义异常:")
    try:
        raise FileParsingError("测试文件解析错误", {"file_path": "/test/path"})
    except FileParsingError as e:
        print(f"✓ 文件解析异常: {e}")
        print(f"  错误码: {e.error_code.value[0]}")
        print(f"  状态码: {e.status_code}")
    except Exception as e:
        print(f"✗ 自定义异常类型错误: {e}")
    
    # 测试5: 日志上下文
    print("\n5. 测试日志上下文:")
    logger.info("这是带上下文的日志信息", extra={
        'extra_data': {
            'user_id': 'test_user',
            'operation': 'test_operation',
            'timestamp': '2024-01-01T00:00:00Z'
        }
    })
    print("✓ 日志上下文记录完成")
    
    print("\n" + "=" * 50)
    print("所有测试完成!")
    print("=" * 50)


if __name__ == "__main__":
    try:
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()