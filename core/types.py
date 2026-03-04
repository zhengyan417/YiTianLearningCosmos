"""
轻量的类型定义，便于在跨进程/跨服务传递数据时减少 Any。
如果后续接入 mypy/pyright，可直接引用这些 TypedDict / Protocol。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, TypedDict


class MessagePayload(TypedDict, total=False):
    role: str
    parts: List[Any]
    message_id: Optional[str]
    context_id: Optional[str]
    task_id: Optional[str]
    metadata: Dict[str, Any]


class TaskStatusPayload(TypedDict, total=False):
    state: Optional[str]
    message: Optional[MessagePayload]
    metadata: Dict[str, Any]


class TaskPayload(TypedDict, total=False):
    id: Optional[str]
    context_id: Optional[str]
    status: Optional[TaskStatusPayload]
    artifacts: Optional[List[Any]]
    metadata: Dict[str, Any]


class EventProtocol(Protocol):
    """最小事件协议，供监控/序列化时做类型提示。"""

    def model_dump(self) -> Dict[str, Any]: ...

