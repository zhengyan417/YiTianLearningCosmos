"""
A2A 通信监控模块
用于记录和追踪 A2A 服务器与客户端之间的所有数据交换
记录内容包括：传输内容、数据大小、时间戳、元数据等
"""

import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Callable
from functools import wraps
import asyncio

PROJECT_ROOT = Path(__file__).resolve().parents[1]

from core.security import redact_any
from core.streaming import (
    STREAM_PROTOCOL_VERSION,
    ENDPOINT_REQUEST,
    ENDPOINT_RESPONSE,
    ENDPOINT_STREAM_CHUNK,
    ENDPOINT_ERROR,
)


def _extract_payload(data: Any) -> Any:
    """
    Safely convert an arbitrary A2A object (Message/Task/events) to a
    serialisable structure for logging while keeping as much detail as possible.
    """
    if data is None:
        return None
    if isinstance(data, (str, bytes, dict, list, int, float, bool)):
        return data
    for attr in ("model_dump", "dict"):
        if hasattr(data, attr):
            try:
                return getattr(data, attr)()
            except Exception:
                pass
    if hasattr(data, "json"):
        try:
            return json.loads(data.json())
        except Exception:
            pass
    try:
        return str(data)
    except Exception:
        return "[unserializable]"


# A2A core types (optional import; used for isinstance checks)
try:
    from a2a.types import (
        Message,
        Task,
        TaskStatusUpdateEvent,
        TaskArtifactUpdateEvent,
    )
except Exception:  # pragma: no cover - allow module import without SDK
    Message = Task = TaskStatusUpdateEvent = TaskArtifactUpdateEvent = None  # type: ignore


class A2AMonitorLogger:
    """A2A 通信专用日志记录器"""
    
    def __init__(
        self,
        log_dir: Optional[str] = None,
        log_filename: str = "a2a_comm.log",
        max_bytes: int = 50 * 1024 * 1024,  # 50MB
        backup_count: int = 10,
        log_level: str = "INFO"
    ):
        """
        初始化监控日志记录器
        
        Args:
            log_dir: 日志目录
            log_filename: 日志文件名
            max_bytes: 单个日志文件最大大小
            backup_count: 保留的备份文件数量
            log_level: 日志级别
        """
        # 默认使用项目根下的 logs/a2a_communication，避免因 cwd 变化写入子目录
        if log_dir is None:
            self.log_dir = PROJECT_ROOT / "logs" / "a2a_communication"
        else:
            self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_file = self.log_dir / log_filename
        
        # 创建专用的 logger
        self.logger = logging.getLogger("a2a_communication_monitor")
        self.logger.setLevel(getattr(logging, log_level.upper()))
        self.logger.propagate = False  # 不传播到根 logger
        
        # 清除现有处理器
        self.logger.handlers.clear()
        
        # 文件处理器 - 使用轮转
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        
        # 自定义 JSON 格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # 可选的控制台处理器（调试用）
        if os.getenv("A2A_MONITOR_CONSOLE", "False").lower() == "true":
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        self.logger.info("=" * 80)
        self.logger.info("A2A 通信监控模块已启动")
        self.logger.info("=" * 80)
    
    def log_communication(
        self,
        direction: str,  # "client_to_server" or "server_to_client"
        endpoint_type: str,  # "request" | "response" | "stream_chunk" | "error"
        data: Any,
        metadata: Optional[Dict[str, Any]] = None,
        context_id: Optional[str] = None,
        task_id: Optional[str] = None,
        message_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        streaming: bool = False,
        chunk_index: Optional[int] = None,
    ):
        """
        记录通信事件
        
        Args:
            direction: 通信方向 ("client_to_server" | "server_to_client")
            endpoint_type: 端点类型 ("request" | "response" | "stream_chunk")
            data: 传输的数据内容
            metadata: 额外的元数据
            context_id: 上下文 ID
            task_id: 任务 ID
            message_id: 消息 ID
            agent_name: 智能体名称
            streaming: 是否是流式传输
            chunk_index: 流式分块索引（如果是流式传输）
        """
        # 先将对象转换为可序列化格式，避免在日志中丢失关键信息
        payload = _extract_payload(data)

        # 计算数据大小
        data_size = self._calculate_data_size(payload)
        
        # 构建日志条目
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "direction": direction,
            "endpoint_type": endpoint_type,
            "stream_protocol": STREAM_PROTOCOL_VERSION,
            "data_size_bytes": data_size,
            "data_size_human": self._format_size(data_size),
            "streaming": streaming,
        }
        
        # 添加可选字段
        if context_id:
            log_entry["context_id"] = context_id
        if task_id:
            log_entry["task_id"] = task_id
        if message_id:
            log_entry["message_id"] = message_id
        if agent_name:
            log_entry["agent_name"] = agent_name
        if chunk_index is not None:
            log_entry["chunk_index"] = chunk_index
        
        # 添加元数据
        if metadata:
            log_entry["metadata"] = redact_any(_extract_payload(metadata))
        
        # 添加数据内容（序列化）
        log_entry["data_preview"] = self._serialize_data(redact_any(payload))
        
        # 记录日志
        self.logger.info(json.dumps(log_entry, ensure_ascii=False))
        
        return log_entry
    
    def _calculate_data_size(self, data: Any) -> int:
        """计算数据大小（字节）"""
        try:
            if isinstance(data, (str, bytes)):
                return len(data.encode('utf-8') if isinstance(data, str) else data)
            elif isinstance(data, (dict, list)):
                return len(json.dumps(data, ensure_ascii=False).encode('utf-8'))
            else:
                return len(str(data).encode('utf-8'))
        except Exception:
            return 0
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化数据大小显示"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
    
    def _serialize_data(self, data: Any, max_length: int = 2000) -> str:
        """序列化数据为字符串预览"""
        try:
            if isinstance(data, (dict, list)):
                serialized = json.dumps(data, ensure_ascii=False, default=str)
            else:
                serialized = str(data)
            
            # 截断过长的数据
            if len(serialized) > max_length:
                serialized = serialized[:max_length] + f"... [truncated, total length: {len(serialized)}]"
            
            return serialized
        except Exception as e:
            return f"[Serialization Error: {e}]"
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """获取日志统计信息"""
        try:
            # 读取最新的日志文件
            if not self.log_file.exists():
                return {"error": "No log file found"}
            
            stats = {
                "total_entries": 0,
                "client_to_server": 0,
                "server_to_client": 0,
                "total_data_transferred": 0,
                "streaming_events": 0,
                "unique_contexts": set(),
                "unique_tasks": set(),
            }
            
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        # 提取 JSON 部分（跳过时间戳前缀）
                        json_part = line.split(' - ', 1)[1] if ' - ' in line else line
                        entry = json.loads(json_part)
                        
                        stats["total_entries"] += 1
                        
                        if entry.get("direction") == "client_to_server":
                            stats["client_to_server"] += 1
                        elif entry.get("direction") == "server_to_client":
                            stats["server_to_client"] += 1
                        
                        stats["total_data_transferred"] += entry.get("data_size_bytes", 0)
                        
                        if entry.get("streaming"):
                            stats["streaming_events"] += 1
                        
                        if "context_id" in entry:
                            stats["unique_contexts"].add(entry["context_id"])
                        if "task_id" in entry:
                            stats["unique_tasks"].add(entry["task_id"])
                    
                    except (json.JSONDecodeError, IndexError):
                        continue
            
            # 转换集合为计数
            stats["unique_contexts"] = len(stats["unique_contexts"])
            stats["unique_tasks"] = len(stats["unique_tasks"])
            stats["total_data_transferred_human"] = self._format_size(stats["total_data_transferred"])
            
            return stats
        
        except Exception as e:
            return {"error": str(e)}


# 全局监控实例
_a2a_monitor: Optional[A2AMonitorLogger] = None


def get_monitor() -> A2AMonitorLogger:
    """获取或创建全局监控实例"""
    global _a2a_monitor
    if _a2a_monitor is None:
        _a2a_monitor = A2AMonitorLogger()
    return _a2a_monitor


def monitor_client_request(func: Callable) -> Callable:
    """
    装饰器：监控客户端请求
    
    用法：
    @monitor_client_request
    async def send_message_streaming(self, request):
        ...
    """
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        monitor = get_monitor()
        
        # 提取请求参数
        request = args[0] if args else kwargs.get('request')
        request_dict = _extract_payload(request)
        context_id = None
        task_id = None
        message_id = None
        if isinstance(request_dict, dict):
            context_id = request_dict.get('params', {}).get('message', {}).get('context_id')
            task_id = request_dict.get('params', {}).get('message', {}).get('task_id')
            message_id = request_dict.get('params', {}).get('message', {}).get('message_id')
        
        # 记录请求
        if request_dict is not None:
            monitor.log_communication(
                direction="client_to_server",
                endpoint_type="request",
                data=request_dict,
                context_id=context_id,
                task_id=task_id,
                message_id=message_id,
            )
        
        # 执行原始方法
        result = await func(self, *args, **kwargs)
        
        return result
    
    return wrapper


def monitor_agent_execution(func: Callable) -> Callable:
    """
    装饰器：监控服务器端 Agent 执行
    
    用法：
    @monitor_agent_execution
    async def execute(self, context, event_queue):
        ...
    """
    @wraps(func)
    async def wrapper(self, context, event_queue, *args, **kwargs):
        monitor = get_monitor()
        
        # 获取智能体名称
        agent_name = self.__class__.__name__
        
        # 提取上下文信息
        context_id = getattr(context, "context_id", None)
        task_id = getattr(context, "task_id", None)
        message_id = None
        query = None
        request_snapshot = None
        
        if hasattr(context, "message") and context.message:
            msg = context.message
            request_snapshot = _extract_payload(msg)
            message_id = getattr(msg, "message_id", None)
            context_id = context_id or getattr(msg, "context_id", None)
            task_id = task_id or getattr(msg, "task_id", None)
        
        if hasattr(context, 'get_user_input'):
            query = context.get_user_input()
        
        # 记录请求（包含原始消息与解析出的用户输入）
        monitor.log_communication(
            direction="client_to_server",
            endpoint_type="request",
            data=request_snapshot or {"query": query},
            metadata={"query": query} if query else None,
            context_id=context_id,
            task_id=task_id,
            message_id=message_id,
            agent_name=agent_name,
        )
        
        # 执行原始方法并监控响应
        original_enqueue = event_queue.enqueue_event
        chunk_counter = {"idx": 0}
        
        async def monitored_enqueue_event(event):
            chunk_counter["idx"] += 1
            event_data = _extract_payload(event)
            
            endpoint_type = "response"
            streaming = False
            if TaskStatusUpdateEvent and isinstance(event, TaskStatusUpdateEvent):
                streaming = True
                endpoint_type = "stream_chunk"
            elif TaskArtifactUpdateEvent and isinstance(event, TaskArtifactUpdateEvent):
                streaming = True
                endpoint_type = "stream_chunk"
            elif Task and isinstance(event, Task):
                streaming = True
                endpoint_type = "stream_chunk" if getattr(event, "status", None) else "response"
            elif Message and isinstance(event, Message):
                endpoint_type = "response"
            elif hasattr(event, "status"):
                streaming = True
                endpoint_type = "stream_chunk"
            
            event_context_id = getattr(event, "context_id", context_id)
            event_task_id = getattr(event, "task_id", None) or getattr(event, "id", task_id)
            event_message_id = getattr(event, "message_id", None)
            
            monitor.log_communication(
                direction="server_to_client",
                endpoint_type=endpoint_type,
                data=event_data,
                context_id=event_context_id,
                task_id=event_task_id,
                message_id=event_message_id,
                agent_name=agent_name,
                streaming=streaming,
                chunk_index=chunk_counter["idx"] if streaming else None,
            )
            
            return await original_enqueue(event)
        
        try:
            # 临时替换 enqueue 方法
            event_queue.enqueue_event = monitored_enqueue_event
            
            # 执行
            result = await func(self, context, event_queue, *args, **kwargs)
            return result
        
        except Exception as e:
            # 记录错误
            monitor.log_communication(
                direction="server_to_client",
                endpoint_type="error",
                data={"error": str(e), "type": type(e).__name__},
                context_id=context_id,
                task_id=task_id,
                agent_name=agent_name,
            )
            raise
        finally:
            # 恢复原始方法
            event_queue.enqueue_event = original_enqueue
    
    return wrapper


# 便捷函数
def log_manual_communication(
    direction: str,
    data: Any,
    context_id: Optional[str] = None,
    task_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    **metadata
):
    """手动记录通信事件"""
    monitor = get_monitor()
    return monitor.log_communication(
        direction=direction,
        endpoint_type="manual",
        data=data,
        context_id=context_id,
        task_id=task_id,
        agent_name=agent_name,
        metadata=metadata or None
    )


# 自动初始化
if os.getenv("ENABLE_A2A_MONITORING", "False").lower() == "true":
    get_monitor()
