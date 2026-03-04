"""
观测统一入口
提供统一的日志配置、获取 logger，以及复用 A2A 通信监控实例。
"""

from __future__ import annotations

import logging
from typing import Optional

import core.bootstrap  # 确保项目根路径
from core import logging_config
from core.a2a_monitor import get_monitor, A2AMonitorLogger


def setup_logging(level: str = "INFO", console: bool = True, json_format: bool = False) -> None:
    """
    快速设置基础日志。
    - level: 日志级别字符串
    - console: 是否输出到控制台
    - json_format: 是否使用 JSON 格式（委托给 logging_config）
    """
    logging_config.configure_logging(
        level=level,
        console=console,
        json_format=json_format,
    )


def get_logger(name: str) -> logging.Logger:
    """统一获取 logger，内部复用 logging_config 配置。"""
    return logging_config.get_logger(name)


def monitor() -> A2AMonitorLogger:
    """获取 A2A 通信监控实例。"""
    return get_monitor()


__all__ = ["setup_logging", "get_logger", "monitor"]
