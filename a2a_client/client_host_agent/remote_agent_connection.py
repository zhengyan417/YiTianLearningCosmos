import traceback

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


TaskCallbackArg = Task | TaskStatusUpdateEvent | TaskArtifactUpdateEvent # 任务更新回调参数
TaskUpdateCallback = Callable[[TaskCallbackArg, AgentCard], Task] # 任务更新回调

# 与远程agent建立连接
class RemoteAgentConnections:
    """与远程智能体创建连接"""

    def __init__(self, client_factory: ClientFactory, agent_card: AgentCard): # 初始化
        self.agent_client: Client = client_factory.create(agent_card) # 创建客户端
        self.card: AgentCard = agent_card # 创建智能体卡片
        self.pending_tasks = set() # 待处理的任务

    def get_agent(self) -> AgentCard: # 获取智能体卡片
        return self.card # 返回智能体卡片

    async def send_message(self, message: Message) -> Task | Message | None: # 发送信息
        lastTask: Task | None = None # 初始化最后一个任务
        try:
            async for event in self.agent_client.send_message(message): # 获取事件
                if isinstance(event, Message): # 如果是消息
                    return event # 直接返回事件
                if self.is_terminal_or_interrupted(event[0]): # 如果当前事件是终态或者被中断
                    return event[0] # 直接返回事件
                lastTask = event[0] # 获取最后一个任务
        except Exception as e:
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
