"""
统一的异常处理装饰器
用于包装异步函数，提供一致的错误处理和日志记录
"""

import functools
import traceback
from typing import Callable, Any, TypeVar, cast
import asyncio
import inspect

from .exceptions import (
    BaseAppException, 
    InternalServerError, 
    ValidationError,
    AgentUnavailableError,
    ModelCallError,
    FileParsingError,
    APICallError,
    ConfigError,
    EnvironmentError
)
from .logging_config import get_logger, log_exception

# 类型变量定义
F = TypeVar('F', bound=Callable[..., Any])

logger = get_logger(__name__)


def handle_exceptions(
    func: F,
    reraise_internal: bool = False,
    default_return_value: Any = None
) -> F:
    """
    异常处理装饰器
    
    Args:
        func: 被装饰的函数
        reraise_internal: 是否重新抛出内部错误
        default_return_value: 发生错误时的默认返回值
    
    Returns:
        装饰后的函数
    """
    
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except BaseAppException as e:
                # 应用层异常，记录并重新抛出
                log_exception(logger, e, {
                    'function': func.__name__,
                    'args': str(args)[:100],  # 限制参数长度
                    'kwargs': str(kwargs.keys())
                })
                raise
            except ValidationError as e:
                logger.warning(f"参数验证失败: {e}", extra={
                    'function': func.__name__,
                    'validation_error': str(e)
                })
                raise
            except (ConnectionError, TimeoutError) as e:
                logger.error(f"网络连接错误: {e}", extra={
                    'function': func.__name__,
                    'error_type': type(e).__name__
                })
                raise AgentUnavailableError(f"服务连接失败: {str(e)}")
            except ValueError as e:
                logger.warning(f"参数值错误: {e}", extra={
                    'function': func.__name__
                })
                raise ValidationError(str(e))
            except KeyError as e:
                logger.warning(f"缺少必要配置: {e}", extra={
                    'function': func.__name__
                })
                raise EnvironmentError(f"环境变量缺失: {str(e)}")
            except ImportError as e:
                logger.error(f"依赖导入失败: {e}", extra={
                    'function': func.__name__
                })
                raise ConfigError(f"依赖配置错误: {str(e)}")
            except Exception as e:
                # 未预期的异常
                log_exception(logger, e, {
                    'function': func.__name__,
                    'unexpected_error': True
                })
                
                if reraise_internal:
                    raise InternalServerError(f"函数 {func.__name__} 执行失败: {str(e)}")
                return default_return_value
                
        return cast(F, async_wrapper)
    else:
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except BaseAppException as e:
                log_exception(logger, e, {
                    'function': func.__name__,
                    'args': str(args)[:100],
                    'kwargs': str(kwargs.keys())
                })
                raise
            except ValidationError as e:
                logger.warning(f"参数验证失败: {e}", extra={
                    'function': func.__name__
                })
                raise
            except (ConnectionError, TimeoutError) as e:
                logger.error(f"网络连接错误: {e}", extra={
                    'function': func.__name__
                })
                raise AgentUnavailableError(f"服务连接失败: {str(e)}")
            except ValueError as e:
                logger.warning(f"参数值错误: {e}", extra={
                    'function': func.__name__
                })
                raise ValidationError(str(e))
            except KeyError as e:
                logger.warning(f"缺少必要配置: {e}", extra={
                    'function': func.__name__
                })
                raise EnvironmentError(f"环境变量缺失: {str(e)}")
            except ImportError as e:
                logger.error(f"依赖导入失败: {e}", extra={
                    'function': func.__name__
                })
                raise ConfigError(f"依赖配置错误: {str(e)}")
            except Exception as e:
                log_exception(logger, e, {
                    'function': func.__name__,
                    'unexpected_error': True
                })
                
                if reraise_internal:
                    raise InternalServerError(f"函数 {func.__name__} 执行失败: {str(e)}")
                return default_return_value
                
        return cast(F, sync_wrapper)


def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    exponential_backoff: bool = True,
    exceptions: tuple = (Exception,)
):
    """
    重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间（秒）
        exponential_backoff: 是否使用指数退避
        exceptions: 需要重试的异常类型元组
    """
    def decorator(func: F) -> F:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exception = None
                for attempt in range(max_retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        if attempt < max_retries:
                            current_delay = delay * (2 ** attempt) if exponential_backoff else delay
                            logger.warning(
                                f"函数 {func.__name__} 第 {attempt + 1} 次执行失败，"
                                f"{current_delay} 秒后重试: {e}"
                            )
                            await asyncio.sleep(current_delay)
                        else:
                            logger.error(
                                f"函数 {func.__name__} 重试 {max_retries} 次后仍然失败: {e}"
                            )
                
                raise last_exception
            
            return cast(F, async_wrapper)
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                import time
                last_exception = None
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_exception = e
                        if attempt < max_retries:
                            current_delay = delay * (2 ** attempt) if exponential_backoff else delay
                            logger.warning(
                                f"函数 {func.__name__} 第 {attempt + 1} 次执行失败，"
                                f"{current_delay} 秒后重试: {e}"
                            )
                            time.sleep(current_delay)
                        else:
                            logger.error(
                                f"函数 {func.__name__} 重试 {max_retries} 次后仍然失败: {e}"
                            )
                
                raise last_exception
            
            return cast(F, sync_wrapper)
    
    return decorator


def with_logging_context(**context_kwargs):
    """
    为函数添加日志上下文的装饰器
    
    Args:
        **context_kwargs: 要添加到日志上下文的键值对
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # 添加上下文到日志记录
            extra_context = {
                'function_context': {
                    **context_kwargs,
                    'function_name': func.__name__
                }
            }
            
            logger.info(f"开始执行函数: {func.__name__}", extra=extra_context)
            try:
                result = await func(*args, **kwargs)
                logger.info(f"函数执行成功: {func.__name__}", extra=extra_context)
                return result
            except Exception as e:
                logger.error(f"函数执行失败: {func.__name__} - {e}", extra=extra_context)
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            extra_context = {
                'function_context': {
                    **context_kwargs,
                    'function_name': func.__name__
                }
            }
            
            logger.info(f"开始执行函数: {func.__name__}", extra=extra_context)
            try:
                result = func(*args, **kwargs)
                logger.info(f"函数执行成功: {func.__name__}", extra=extra_context)
                return result
            except Exception as e:
                logger.error(f"函数执行失败: {func.__name__} - {e}", extra=extra_context)
                raise
        
        # 根据原函数类型返回相应的包装器
        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        else:
            return cast(F, sync_wrapper)
    
    return decorator


# 便捷装饰器组合
def robust_api_call(
    max_retries: int = 3,
    reraise_internal: bool = True
):
    """
    健壮的API调用装饰器组合
    
    Args:
        max_retries: 重试次数
        reraise_internal: 是否重新抛出内部错误
    """
    def decorator(func: F) -> F:
        # 组合装饰器：重试 -> 异常处理 -> 日志上下文
        decorated = with_logging_context(component="api_call")(func)
        decorated = retry_on_failure(
            max_retries=max_retries,
            exceptions=(ConnectionError, TimeoutError, APICallError)
        )(decorated)
        decorated = handle_exceptions(
            decorated, 
            reraise_internal=reraise_internal
        )
        return decorated
    return decorator