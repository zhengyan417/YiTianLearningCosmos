"""
自定义异常类定义
统一的异常处理体系，便于错误识别和处理
"""

from typing import Optional, Any
from enum import Enum


class ErrorCode(Enum):
    """错误码枚举"""
    # 通用错误
    INTERNAL_ERROR = ("INTERNAL_ERROR", "系统内部错误")
    VALIDATION_ERROR = ("VALIDATION_ERROR", "参数验证失败")
    NOT_FOUND = ("NOT_FOUND", "资源未找到")
    UNAUTHORIZED = ("UNAUTHORIZED", "未授权访问")
    FORBIDDEN = ("FORBIDDEN", "禁止访问")
    
    # 业务错误
    AGENT_UNAVAILABLE = ("AGENT_UNAVAILABLE", "智能体服务不可用")
    MODEL_ERROR = ("MODEL_ERROR", "模型调用失败")
    PARSING_ERROR = ("PARSING_ERROR", "文件解析失败")
    API_CALL_ERROR = ("API_CALL_ERROR", "外部API调用失败")
    
    # 配置错误
    CONFIG_ERROR = ("CONFIG_ERROR", "配置错误")
    ENV_ERROR = ("ENV_ERROR", "环境变量缺失")


class BaseAppException(Exception):
    """应用基础异常类"""
    
    def __init__(
        self, 
        error_code: ErrorCode, 
        message: Optional[str] = None,
        details: Optional[Any] = None,
        status_code: int = 500
    ):
        self.error_code = error_code
        self.message = message or error_code.value[1]
        self.details = details
        self.status_code = status_code
        super().__init__(self.message)
    
    def __str__(self):
        return f"[{self.error_code.value[0]}] {self.message}"
    
    def to_dict(self):
        """转换为字典格式，便于API响应"""
        return {
            "error_code": self.error_code.value[0],
            "message": self.message,
            "details": self.details,
            "status_code": self.status_code
        }


# 具体异常类定义
class InternalServerError(BaseAppException):
    """内部服务器错误"""
    def __init__(self, message: Optional[str] = None, details: Optional[Any] = None):
        super().__init__(ErrorCode.INTERNAL_ERROR, message, details, 500)


class ValidationError(BaseAppException):
    """参数验证错误"""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(ErrorCode.VALIDATION_ERROR, message, details, 400)


class NotFoundError(BaseAppException):
    """资源未找到错误"""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(ErrorCode.NOT_FOUND, message, details, 404)


class UnauthorizedError(BaseAppException):
    """未授权错误"""
    def __init__(self, message: str = "未授权访问", details: Optional[Any] = None):
        super().__init__(ErrorCode.UNAUTHORIZED, message, details, 401)


class ForbiddenError(BaseAppException):
    """禁止访问错误"""
    def __init__(self, message: str = "禁止访问", details: Optional[Any] = None):
        super().__init__(ErrorCode.FORBIDDEN, message, details, 403)


class AgentUnavailableError(BaseAppException):
    """智能体服务不可用"""
    def __init__(self, message: str = "智能体服务暂时不可用", details: Optional[Any] = None):
        super().__init__(ErrorCode.AGENT_UNAVAILABLE, message, details, 503)


class ModelCallError(BaseAppException):
    """模型调用错误"""
    def __init__(self, message: str = "模型调用失败", details: Optional[Any] = None):
        super().__init__(ErrorCode.MODEL_ERROR, message, details, 500)


class FileParsingError(BaseAppException):
    """文件解析错误"""
    def __init__(self, message: str = "文件解析失败", details: Optional[Any] = None):
        super().__init__(ErrorCode.PARSING_ERROR, message, details, 400)


class APICallError(BaseAppException):
    """外部API调用错误"""
    def __init__(self, message: str = "外部API调用失败", details: Optional[Any] = None):
        super().__init__(ErrorCode.API_CALL_ERROR, message, details, 502)


class ConfigError(BaseAppException):
    """配置错误"""
    def __init__(self, message: str = "配置错误", details: Optional[Any] = None):
        super().__init__(ErrorCode.CONFIG_ERROR, message, details, 500)


class EnvironmentError(BaseAppException):
    """环境变量错误"""
    def __init__(self, message: str = "环境变量配置错误", details: Optional[Any] = None):
        super().__init__(ErrorCode.ENV_ERROR, message, details, 500)