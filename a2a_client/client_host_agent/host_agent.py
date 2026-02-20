import asyncio
import base64
import json
import os
import sys
from typing import Optional
import uuid

import httpx

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import (
    AgentCard,
    DataPart,
    Message,
    FilePart,
    FileWithBytes,
    Part,
    Role,
    Task,
    TaskState,
    TextPart,
    TransportProtocol,
)
from dotenv import load_dotenv
from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.tool_context import ToolContext
from google.genai import types
from remote_agent_connection import *
from timestamp_ext import TimestampExtension

load_dotenv()

class HostAgent:
    """The host agent.

    This is the agent responsible for choosing which remote agents to send
    tasks to and coordinate their work.
    """

    def __init__(
        self,
        remote_agent_addresses: list[str],
        http_client: httpx.AsyncClient,
        task_callback: TaskUpdateCallback | None = None,
    ):
        self.task_callback = task_callback
        self.httpx_client = http_client
        self.timestamp_extension = TimestampExtension()
        config = ClientConfig(
            httpx_client=self.httpx_client,
            supported_transports=[
                TransportProtocol.jsonrpc,
                TransportProtocol.http_json,
            ],
        )
        client_factory = ClientFactory(config)
        client_factory = self.timestamp_extension.wrap_client_factory(
            client_factory
        )
        self.client_factory = client_factory
        self.remote_agent_connections: dict[str, RemoteAgentConnections] = {}
        self.cards: dict[str, AgentCard] = {}
        self.agents: str = ''
        loop = asyncio.get_running_loop()
        loop.create_task(
            self.init_remote_agent_addresses(remote_agent_addresses)
        )

    # 获取所有的远程的agent的信息
    async def init_remote_agent_addresses(
        self, remote_agent_addresses: list[str]
    ):
        async with asyncio.TaskGroup() as task_group:
            for address in remote_agent_addresses:
                task_group.create_task(self.retrieve_card(address))
        # The task groups run in the background and complete.
        # Once completed the self.agents string is set and the remote
        # connections are established.

    # 获取agent card
    async def retrieve_card(self, address: str):
        card_resolver = A2ACardResolver(self.httpx_client, address)
        card = await card_resolver.get_agent_card()
        self.register_agent_card(card)

    # 注册agent card
    def register_agent_card(self, card: AgentCard):
        remote_connection = RemoteAgentConnections(self.client_factory, card)
        self.remote_agent_connections[card.name] = remote_connection
        self.cards[card.name] = card
        agent_info = []
        for ra in self.list_remote_agents():
            agent_info.append(json.dumps(ra))
        self.agents = '\n'.join(agent_info)

    # 创建client agent
    def create_agent(self) -> Agent:
        return Agent(
            model=LiteLlm(
                model="deepseek/deepseek-chat",
                api_key=os.environ.get('DEEPSEEK_API_KEY'),
                base_url="https://api.deepseek.com"
            ),
            name='client_host_agent',
            instruction=self.root_instruction,
            before_model_callback=self.before_model_callback,
            description=(
                'This agent orchestrates the decomposition of the user request into'
                ' tasks that can be performed by the child agents.'
            ),
            tools=[
                self.list_remote_agents,
                self.send_message,
            ],
        )

    def root_instruction(self, context: ReadonlyContext) -> str:
        current_agent = self.check_state(context)
        return f"""您是一位擅长将用户请求分派给相应远程智能体的专家。

**发现：**
- 您可以使用 `list_remote_agents` 来列出可用的远程智能体，以便将任务分派给它们。

**执行：**
- 对于可执行的请求，您可以使用 `send_message` 与远程智能体进行交互，以采取行动。

**请务必在回复用户时注明远程智能体的名称。**

请确保依靠工具来处理请求，不要自行编造回应。如果您不确定，请向用户询问更多细节。
请主要关注对话中最新部分的内容。

**可用智能体：**
{self.agents}

**当前智能体：**
{current_agent['active_agent']}
"""

    # 检查不同A2A server状态
    def check_state(self, context: ReadonlyContext):
        state = context.state
        if (
            'context_id' in state
            and 'session_active' in state
            and state['session_active']
            and 'agent' in state
        ):
            return {'active_agent': f'{state["agent"]}'}
        return {'active_agent': 'None'}

    def before_model_callback(
        self, callback_context: CallbackContext, llm_request
    ):
        state = callback_context.state
        if 'session_active' not in state or not state['session_active']:
            state['session_active'] = True

    # 列出远程可以的使用的智能体的信息
    def list_remote_agents(self):
        """List the available remote agents you can use to delegate the task."""
        if not self.remote_agent_connections:
            return []

        remote_agent_info = []
        for card in self.cards.values():
            remote_agent_info.append(
                {'name': card.name, 'description': card.description}
            )
        return remote_agent_info

    # 发送信息
    async def send_message(
        self, agent_name: str, message: str, tool_context: ToolContext, file_path: Optional[str] = None
    ):
        """向指定远程智能体发送消息和可选的文件附件。

        此方法会向名为 agent_name 的远程智能体发送一个任务请求，支持流式（如果智能体支持）或非流式响应。
        现在增加了文件传输功能，可以发送本地文件作为消息附件。

        Args:
          agent_name: 接收消息的远程智能体名称。
          message: 要发送给智能体的文本消息内容。
          tool_context: 该方法运行所在的工具上下文。
          file_path: （可选）要附加的本地文件路径。如果提供，文件内容将被编码并随消息一起发送。

        Yields:
          返回一个包含JSON数据的字典。
        
        Raises:
          ValueError: 当指定的智能体不存在或客户端不可用时抛出。
        """
        # 前置验证
        if agent_name not in self.remote_agent_connections:
            raise ValueError(f'{agent_name}没有找到')
        # 1. 获取当前状态
        state = tool_context.state
        state['agent'] = agent_name
        client = self.remote_agent_connections[agent_name]
        if not client:
            raise ValueError(f'{agent_name}A2A客户端不可用')
        task_id = state.get('task_id', None)
        context_id = state.get('context_id', None)
        message_id = state.get('message_id', None)
        # task: Task
        if not message_id:
            message_id = str(uuid.uuid4())

        # 2. 建立信息格式
        request_message = Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=message))],
            message_id=message_id,
            context_id=context_id,
            task_id=task_id,
        )
        # 如果有要添加文件
        if file_path and file_path.strip() != '': # 如果文件路径存在
            with open(file_path, 'rb') as f: # 打开文件
                file_content = base64.b64encode(f.read()).decode('utf-8') # 解码文件内容
                file_name = os.path.basename(file_path) # 获取文件名

            request_message.parts.append( # 将文件内容加入消息里面
                Part( # 构建文件内容
                    root=FilePart( # 创建文件内容
                        file=FileWithBytes(name=file_name, bytes=file_content) # 文件内容
                    )
                )
            )
        
        # 3. 发送信息，增加重试机制和异常处理
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                response = await client.send_message(request_message)
                break  # 成功则跳出循环
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    # 最后的错误处理
                    error_msg = f"与代理 {agent_name} 通信失败，已尝试 {max_retries} 次重试。错误详情: {str(e)}"
                    print(f"----发送消息的时候出现了异常-----")
                    print(error_msg)
                    print(f"错误类型: {type(e).__name__}")
                    import traceback
                    traceback.print_exc()
                    
                    # 返回友好的错误信息而不是抛出异常
                    return [f"很抱歉，与代理 {agent_name} 的通信出现故障，请稍后重试或联系管理员。"]
                
                # 等待一段时间再重试
                wait_time = 2 ** retry_count  # 指数退避
                print(f"与代理 {agent_name} 通信失败，第 {retry_count} 次重试前等待 {wait_time} 秒...")
                await asyncio.sleep(wait_time)
        
        # 4. 分析response
        # 4.1 message：转换格式后直接返回
        if isinstance(response, Message):
            return await convert_parts(response.parts, tool_context)

        # 4.2 task: 判断task状态
        task: Task = response

        state['session_active'] = task.status.state not in [
            TaskState.completed,
            TaskState.canceled,
            TaskState.failed,
            TaskState.unknown,
        ]
        # 更新状态
        if task.context_id:
            state['context_id'] = task.context_id
        state['task_id'] = task.id
        # 需要用户额外输入
        if task.status.state == TaskState.input_required:
            # Force user input back
            tool_context.actions.skip_summarization = True
            tool_context.actions.escalate = True
        # 任务出错
        elif task.status.state == TaskState.canceled:
            return f"任务取消,请稍后再试"
           
        elif task.status.state == TaskState.failed:
            # Raise error for failure
            raise ValueError(f'{agent_name} 任务 {task.id} 失败')
        response = []
        state['task_id'] = None
        if task.status.message:
            # Assume the information is in the task message.

            # timestamp扩展
            if ts := self.timestamp_extension.get_timestamp(
                task.status.message
            ):
                response.append(f'[at {ts.astimezone().isoformat()}]')
            response.extend(
                await convert_parts(task.status.message.parts, tool_context)
            )
        if task.artifacts:
            for artifact in task.artifacts:
                if ts := self.timestamp_extension.get_timestamp(artifact):
                    response.append(f'[at {ts.astimezone().isoformat()}]')
                response.extend(
                    await convert_parts(artifact.parts, tool_context)
                )
        return response

# 转换格式工具函数
async def convert_parts(parts: list[Part], tool_context: ToolContext):
    rval = []
    for p in parts:
        rval.append(await convert_part(p, tool_context))
    return rval

async def convert_part(part: Part, tool_context: ToolContext):
    if part.root.kind == 'text':
        return part.root.text
    if part.root.kind == 'data':
        return part.root.data
    # 处理文件
    if part.root.kind == 'file':
        # Repackage A2A FilePart to google.genai Blob
        # Currently not considering plain text as files
        file_id = part.root.file.name
        file_bytes = base64.b64decode(part.root.file.bytes)
        file_part = types.Part(
            inline_data=types.Blob(
                mime_type=part.root.file.mime_type, data=file_bytes
            )
        )
        await tool_context.save_artifact(file_id, file_part)
        tool_context.actions.skip_summarization = True
        tool_context.actions.escalate = True
        return DataPart(data={'artifact-file-id': file_id})
    return f'Unknown type: {part.kind}'
