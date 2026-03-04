"""
统一配置管理
使用 pydantic-settings 读取 .env / 环境变量，并提供类型校验与默认值。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 基础
    PROJECT_NAME: str = "YiTianLearningCosmos"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # LLM / API
    DASHSCOPE_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    # 模型/存储路径
    LLM_MODEL_PATH: Optional[str] = None
    EMBED_PATH: Optional[str] = None
    STORAGE_DIR: str = "./storage"

    # RAG 专用
    LLM_PATH: Optional[str] = None
    RAG_EMBED_PATH: Optional[str] = None
    RAG_STORAGE_DIR: Optional[str] = None

    # 智能体 URL
    FILE_PARSE_AGENT_URL: str = "http://localhost:10001"
    CODE_AGENT_URL: str = "http://localhost:10002"
    RAG_AGENT_URL: str = "http://localhost:10003"
    SEARCH_AGENT_URL: str = "http://localhost:10004"
    RESEARCH_AGENT_URL: str = "http://localhost:10005"

    # 客户端
    CLIENT_WEB_PORT: int = 8030

    # 数据库
    DATABASE_URL: Optional[str] = None
    SEARCH_DB_HOST: str = "localhost"
    SEARCH_DB_PORT: int = 5432
    SEARCH_DB_NAME: str = "search_agent_database"
    SEARCH_DB_USER: str = "postgres"
    SEARCH_DB_PASSWORD: str = "postgres"


# 单例实例
settings = Settings()


def settings_summary() -> str:
    """简易概要，便于在日志中输出（隐去敏感值）。"""
    hidden = lambda v: "***" if v else None
    return (
        f"project={settings.PROJECT_NAME}, "
        f"debug={settings.DEBUG}, "
        f"log_level={settings.LOG_LEVEL}, "
        f"agents=[{settings.FILE_PARSE_AGENT_URL}, "
        f"{settings.CODE_AGENT_URL}, "
        f"{settings.RAG_AGENT_URL}, "
        f"{settings.SEARCH_AGENT_URL}, "
        f"{settings.RESEARCH_AGENT_URL}], "
        f"deepseek_key={hidden(settings.DEEPSEEK_API_KEY)}, "
        f"dashscope_key={hidden(settings.DASHSCOPE_API_KEY)}"
    )
