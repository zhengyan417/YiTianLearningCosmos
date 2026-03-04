import traceback

import os, sys
from pathlib import Path
# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT_UP = PROJECT_ROOT.parent
for candidate in (PROJECT_ROOT, PROJECT_ROOT_UP):
    c = str(candidate)
    if c not in sys.path:
        sys.path.insert(0, c)

import core.bootstrap  # 再次确保路径一致

from collections.abc import Callable

from a2a.client import (
    Client,
    ClientFactory,
)
from a2a.types import (
    AgentCard,
    Message,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatusUpdateEvent,
)
from core.a2a_monitor import get_monitor, _extract_payload


TaskCallbackArg = Task | TaskStatusUpdateEvent | TaskArtifactUpdateEvent # 任务更新回调参数
TaskUpdateCallback = Callable[[TaskCallbackArg, AgentCard], Task] # 任务更新回调

# 与远程agent建立连接
class RemoteAgentConnections:
    """与远程智能体创建连接"""

    def __init__(self, client_factory: ClientFactory, agent_card: AgentCard): # 初始化
        self.agent_client: Client = client_factory.create(agent_card) # 创建客户端
        self.card: AgentCard = agent_card # 创建智能体卡片
        self.pending_tasks = set() # 待处理的任务
        self.monitor = get_monitor()

    def get_agent(self) -> AgentCard: # 获取智能体卡片
        return self.card # 返回智能体卡片

    async def send_message(self, message: Message) -> Task | Message | None: # 发送信息
        lastTask: Task | None = None # 初始化最后一个任务

        # 记录客户端发送请求
        try:
            request_payload = message.model_dump() if hasattr(message, "model_dump") else _extract_payload(message)
            self.monitor.log_communication(
                direction="client_to_server",
                endpoint_type="request",
                data=request_payload,
                context_id=getattr(message, "context_id", None),
                task_id=getattr(message, "task_id", None),
                message_id=getattr(message, "message_id", None),
                agent_name=self.card.name,
                metadata={"agent_url": getattr(self.card, "url", None)},
            )
        except Exception:
            pass

        chunk_index = 0
        try:
            async for event in self.agent_client.send_message(message): # 获取事件
                chunk_index += 1
                event_obj = event[0] if isinstance(event, (list, tuple)) else event

                # 记录服务端返回/流式事件
                try:
                    payload = _extract_payload(event_obj)
                    endpoint_type = "response"
                    streaming = False

                    if isinstance(event_obj, (TaskStatusUpdateEvent, TaskArtifactUpdateEvent)):
                        streaming = True
                        endpoint_type = "stream_chunk"
                    elif isinstance(event_obj, Task):
                        streaming = True
                        endpoint_type = "stream_chunk" if not self.is_terminal_or_interrupted(event_obj) else "response"
                    elif isinstance(event_obj, Message):
                        endpoint_type = "response"
                    elif hasattr(event_obj, "status"):
                        streaming = True
                        endpoint_type = "stream_chunk"

                    self.monitor.log_communication(
                        direction="server_to_client",
                        endpoint_type=endpoint_type,
                        data=payload,
                        context_id=getattr(event_obj, "context_id", getattr(message, "context_id", None)),
                        task_id=getattr(event_obj, "task_id", None) or getattr(event_obj, "id", getattr(message, "task_id", None)),
                        message_id=getattr(event_obj, "message_id", None) or getattr(message, "message_id", None),
                        agent_name=self.card.name,
                        streaming=streaming,
                        chunk_index=chunk_index if streaming else None,
                    )
                except Exception:
                    pass

                if isinstance(event_obj, Message): # 如果是消息
                    return event_obj # 直接返回事件
                if isinstance(event_obj, Task) and self.is_terminal_or_interrupted(event_obj): # 如果当前事件是终态或者被中断
                    return event_obj # 直接返回事件
                if isinstance(event_obj, Task):
                    lastTask = event_obj # 获取最后一个任务
        except Exception as e:
            try:
                self.monitor.log_communication(
                    direction="client_to_server",
                    endpoint_type="error",
                    data={"error": str(e), "type": type(e).__name__},
                    context_id=getattr(message, "context_id", None),
                    task_id=getattr(message, "task_id", None),
                    message_id=getattr(message, "message_id", None),
                    agent_name=self.card.name,
                )
            except Exception:
                pass
            print('----发送消息的时候出现了异常-----') # 打印异常信息
            traceback.print_exc() # 打印异常信息
            raise e # 抛出异常
        return lastTask # 返回最后一个任务

    @staticmethod
    def is_terminal_or_interrupted(task: Task) -> bool: # 检测当前是事件是否结束
        return task.status.state in [ # 如果当前事件属于
            TaskState.completed, # 完成
            TaskState.canceled, # 取消
            TaskState.failed, # 失败
            TaskState.input_required, # 需要输入
            TaskState.unknown, # 未知
        ]
