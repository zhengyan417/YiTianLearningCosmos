import logging
import traceback
from typing import Dict, Any

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    FilePart,
    InternalError,
    InvalidParamsError,
    Part,
    Task,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import are_modalities_compatible, new_agent_text_message
from a2a.utils.errors import ServerError
from agent import (
    ChatResponseEvent,
    InputEvent,
    LogEvent,
    DoctorRAGWorkflow,
)
from llama_index.core.workflow import Context

logger = logging.getLogger(__name__) # 获取日志记录器


class DoctorRAGAgentExecutor(AgentExecutor):

    SUPPORTED_INPUT_TYPES = [
        'text/plain',
    ] # 允许的输入格式
    SUPPORTED_OUTPUT_TYPES = ['text', 'text/plain'] # 允许的输出格式

    def __init__(
        self,
        agent: DoctorRAGWorkflow,
    ): # 初始化
        self.agent = agent # 智能体
        self.ctx_states: Dict[str, Dict[str, Any]] = {} # 存储会话状态

    # 执行方法
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        error = self._validate_request(context) # 验证请求
        if error: # 如果验证失败
            raise ServerError(error=InvalidParamsError()) # 抛出服务器错误

        input_event = self._get_input_event(context) # 获取输入事件
        context_id = context.context_id # 获取会话ID
        task_id = context.task_id # 获取任务ID
        try:
            # 检查这个会话是否已经存在
            print(f'会话状态数量: {len(self.ctx_states)}', flush=True) # 打印会话数量
            saved_ctx_state = self.ctx_states.get(context_id, None) # 获取保存的会话状态

            if saved_ctx_state is not None: # 如果会话状态已经存在
                logger.info(f'从已经保存的上下文中恢复会话:{context_id}') # 输出会话信息
                ctx = Context.from_dict(self.agent, saved_ctx_state) # 从字典中恢复会话状态
                handler = self.agent.run( # 运行智能体
                    start_event=input_event, # 输出事件
                    ctx=ctx, # 上下文
                )
            else: # 如果会话状态不存在
                logger.info(f'启动一个新的会话:{context_id}') # 打印日志
                handler = self.agent.run( # 直接运行智能体
                    start_event=input_event, # 输入事件
                )

            updater = TaskUpdater(event_queue, task_id, context_id) # 创建任务更新器
            await updater.submit() # 提交任务更新
            async for event in handler.stream_events(): # 遍历事件
                if isinstance(event, LogEvent): # 如果是日志事件
                    await updater.update_status( # 将日志信息作为信息更新任务状态
                        TaskState.working, # 任务状态：正在工作
                        new_agent_text_message(event.msg, context_id, task_id), # 创建信息
                    )

            final_response = await handler # 获取最终回复
            if isinstance(final_response, ChatResponseEvent): # 如果是聊天事件
                content = final_response.response # 获取回复内容
                metadata = ( # 创建元数据
                    final_response.citations # 引用
                    if hasattr(final_response, 'citations')
                    else None
                )
                if metadata is not None: # 如果元数据不是空
                    metadata = {str(k): v for k, v in metadata.items()} # 确保元数据是字典类型

                self.ctx_states[context_id] = handler.ctx.to_dict() # 保存会话状态

                await updater.add_artifact( # 添加文件
                    parts=[Part(root=TextPart(text=content))], # 回复内容
                    name='医生RAG回答', # 名称
                    metadata=metadata, # 元数据
                )
                await updater.complete() # 完成任务
            else: # 如果不是聊天事件
                # 创建信息
                msg = new_agent_text_message(f'预期之外的结果: {final_response}', context_id, task_id)
                await updater.failed(msg) # 任务失败

        except Exception as e: # 异常捕获
            logger.error(f'流式输出时出现错误: {e}') # 打印错误信息
            logger.error(traceback.format_exc()) # 打印错误堆栈

            if context_id in self.ctx_states: # 如果会话状态存在
                del self.ctx_states[context_id] # 删除会话状态
            raise ServerError( # 抛出服务器错误
                error=InternalError( # 内部错误
                    message=f'流式输出时出现错误: {e}' # 错误信息
                )
            )

    async def cancel( # 取消方法
        self, request: RequestContext, event_queue: EventQueue # 请求和事件队列
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError()) # 抛出服务器错误

    # 验证请求
    def _validate_request(self, context: RequestContext) -> bool:
        invalidOutput = self._validate_output_modes(
            context, self.SUPPORTED_OUTPUT_TYPES # 允许的输出格式
        ) # 验证输出格式
        return invalidOutput or self._validate_push_config(context) # 验证推送配置

    @staticmethod
    def _get_input_event(context: RequestContext) -> InputEvent: # 获取输入事件
        """提取文本内容"""
        text_parts = [] # 初始化文本部分
        for p in context.message.parts: # 遍历消息部分
            part = p.root # 获取内容
            if isinstance(part, TextPart): # 如果这是文本
                text_parts.append(part.text) # 添加文本部分
            else: # 如果是不支持的文件类型
                raise ValueError(f'医生智能体不支持的输入类型: {type(part)}') # 抛出异常

        return InputEvent(
            msg='\n'.join(text_parts), # 用户消息
        ) # 创建输入事件

    @staticmethod
    def _validate_output_modes( # 验证输出格式
        context: RequestContext, # 上下文
        supported_types: list[str], # 支持的格式
    ) -> bool:
        accepted_output_modes = (
            context.configuration.accepted_output_modes
            if context.configuration
            else []
        ) # 获取接受到的输出格式
        if not are_modalities_compatible(
            accepted_output_modes,
            supported_types,
        ): # 如果是不允许的输出格式
            logger.warning(
                '不允许的输出格式. 接收到 %s, 支持 %s',
                accepted_output_modes,
                supported_types,
            ) # 打印警告
            return True # 返回True
        return False # 返回False

    # 验证推送配置
    @staticmethod
    def _validate_push_config(context: RequestContext) -> bool:
        push_notification_config = (
            context.configuration.push_notification_config # 获取推送配置
            if context.configuration # 如果配置存在的话
            else None # 否则返回None
        ) # 推送配置
        if push_notification_config and not push_notification_config.url: # 推送配置且推送配置的URL不存在
            logger.warning('没有推送URL') # 输出警告
            return True # 返回True

        return False # 返回False