"""
安全与审计辅助
- 提供字段脱敏 / 日志红化工具
"""
from __future__ import annotations

from typing import Any, Mapping

SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "token",
    "access_token",
    "secret",
    "password",
    "signature",
}


def redact_mapping(data: Mapping[str, Any], mask: str = "***") -> dict:
    """对映射类数据按关键字红化，返回新的 dict。"""
    redacted = {}
    for k, v in data.items():
        if isinstance(k, str) and k.lower() in SENSITIVE_KEYS:
            redacted[k] = mask
        else:
            redacted[k] = v
    return redacted


def redact_any(data: Any, mask: str = "***") -> Any:
    """对常见容器类型递归红化；其他类型原样返回。"""
    if isinstance(data, Mapping):
        return {k: redact_any(v, mask) for k, v in redact_mapping(data, mask).items()}
    if isinstance(data, list):
        return [redact_any(v, mask) for v in data]
    return data
