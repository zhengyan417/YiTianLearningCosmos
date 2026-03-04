"""
并发与资源管理工具
- 统一创建 httpx AsyncClient，带超时与可选代理信任开关。
- 如需扩展，可加入 TaskGroup/anyio 工具。
"""

from __future__ import annotations

import httpx


def create_http_client(
    timeout: float | httpx.Timeout = httpx.Timeout(300.0, connect=10.0),
    trust_env: bool = False,
    limits: httpx.Limits | None = None,
) -> httpx.AsyncClient:
    """
    创建统一配置的 AsyncClient：
    - 默认全局超时 300s，连接超时 10s
    - trust_env=False 避免系统代理影响本地调用，可按需开启
    - 可传 limits 控制连接池大小
    """
    if limits is None:
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=50)
    return httpx.AsyncClient(timeout=timeout, trust_env=trust_env, limits=limits)
