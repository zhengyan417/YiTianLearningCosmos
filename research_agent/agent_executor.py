import logging
import os

from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.utils.errors import ServerError
from a2a.utils import new_task, new_agent_text_message
from a2a.types import (
    Part,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)

from research_agent.agent import ResearchAgent
from a2a.server.agent_execution import AgentExecutor, RequestContext

# 导入 A2A 监控模块
from core.a2a_monitor import monitor_agent_execution, get_monitor
monitor_enabled = True
monitor = get_monitor()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ResearchAgentExecutor(AgentExecutor):

    # 1.创建ResearchAgent
    def __init__(self):
        self.agent = ResearchAgent()

    @monitor_agent_execution
    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        query = context.get_user_input()
        task = context.current_task
        if not task:
            task = new_task(context.message) 
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        try:
            async for item in self.agent.stream(query, task.context_id):
                is_task_complete = item['is_task_complete']
                require_user_input = item['require_user_input']

                if not is_task_complete and not require_user_input:
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            item['content'],
                            task.context_id,
                            task.id,
                        ),
                    )
                elif require_user_input:
                    await updater.update_status(
                        TaskState.input_required,
                        new_agent_text_message(
                            item['content'],
                            task.context_id,
                            task.id,
                        ),
                        final=True,
                    )
                    break
                else:
                    await updater.add_artifact(
                        [Part(root=TextPart(text=item['content']))],
                        name='search_result',
                    )
                    await updater.complete()
                    break

        except Exception as e:
            logger.error(f'在流式传输消息的时候出现了错误: {e}')
            # 降级为可读错误结果，避免客户端反复重试导致链路中断。
            await updater.add_artifact(
                [Part(root=TextPart(text=f'研究任务执行失败: {type(e).__name__}: {str(e)}'))],
                name='research_error',
            )
            await updater.complete()

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise ServerError(error=UnsupportedOperationError())
