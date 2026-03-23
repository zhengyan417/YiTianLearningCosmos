import asyncio
import base64
import json
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any, Optional
import uuid

import httpx

# 防御性注入项目根
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT_UP = PROJECT_ROOT.parent
for candidate in (PROJECT_ROOT, PROJECT_ROOT_UP):
    c = str(candidate)
    if c not in sys.path:
        sys.path.insert(0, c)

import core.bootstrap  # 确保项目根路径在 sys.path

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
from remote_agent_connection import RemoteAgentConnections, TaskUpdateCallback
from timestamp_ext import TimestampExtension

load_dotenv()

class HostAgent:
    """The host agent.

    This is the agent responsible for choosing which remote agents to send
    tasks to and coordinate their work.
    """
    AGENT_SESSIONS_KEY = 'agent_sessions'

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
        self._agent_locks: dict[str, asyncio.Lock] = {}
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
                # 跳过空地址，避免无效请求
                if not address:
                    continue
                task_group.create_task(self.retrieve_card(address))
        # The task groups run in the background and complete.
        # Once completed the self.agents string is set and the remote
        # connections are established.

    # 获取agent card
    async def retrieve_card(self, address: str):
        try:
            card_resolver = A2ACardResolver(self.httpx_client, address)
            card = await card_resolver.get_agent_card()
            self.register_agent_card(card)
        except Exception as e:
            # 记录错误但不让异常中断 TaskGroup，其它可用智能体仍可注册
            print(f"[HostAgent] 获取 Agent Card 失败: {address} -> {e}")
            return

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
                self.send_messages_parallel,
            ],
        )

    def root_instruction(self, context: ReadonlyContext) -> str:
        current_agent = self.check_state(context)
        return f"""您是一位擅长将用户请求分派给相应远程智能体的专家。

**发现：**
- 您可以使用 `list_remote_agents` 来列出可用的远程智能体，以便将任务分派给它们。

**执行：**
- 对于可执行的请求，您可以使用 `send_message` 与远程智能体进行交互，以采取行动。
- 如果需要同时调用多个远程智能体，请优先使用 `send_messages_parallel`。
- 只要用户提出了可执行任务，回复前至少调用一次远程工具（`send_message` 或 `send_messages_parallel`），不要只给计划。

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
        active_agent = state.get('agent')
        if not active_agent:
            return {'active_agent': 'None'}

        # 优先使用按 agent 隔离后的会话状态。
        sessions = state.get(self.AGENT_SESSIONS_KEY, {})
        agent_session = sessions.get(active_agent, {})
        if agent_session.get('session_active', False):
            return {'active_agent': f'{active_agent}'}

        # 兼容历史状态结构。
        if state.get('session_active', False):
            return {'active_agent': f'{active_agent}'}
        return {'active_agent': 'None'}

    def before_model_callback(
        self, callback_context: CallbackContext, llm_request
    ):
        state = callback_context.state
        self._ensure_session_map(state)
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
        self,
        agent_name: str,
        message: str,
        tool_context: ToolContext,
        file_path: Optional[str] = None,
    ):
        """向指定远程智能体发送消息和可选的文件附件。

        此方法会向名为 agent_name 的远程智能体发送一个任务请求，支持流式（如果智能体支持）或非流式响应。
        现在增加了文件传输功能，可以发送本地文件作为消息附件。

        Args:
          agent_name: 接收消息的远程智能体名称。
          message: 要发送给智能体的文本消息内容。
          tool_context: 该方法运行所在的工具上下文。
          file_path: （可选）要附加的本地文件路径。如果提供，文件内容将被编码并随消息一起发送。
            当调用支持文件输入的远程智能体（如文档解析智能体）且未提供 file_path 时，
            会尝试自动附加当前会话中最近的文件 artifact。

        Yields:
          返回一个包含JSON数据的字典。
        
        Raises:
          ValueError: 当指定的智能体不存在或客户端不可用时抛出。
        """
        return await self._send_message_internal(
            agent_name=agent_name,
            message=message,
            tool_context=tool_context,
            file_path=file_path,
            sync_legacy_state=True,
        )

    async def send_messages_parallel(
        self,
        requests: list[dict[str, Any]],
        tool_context: ToolContext,
        max_concurrency: Optional[int] = None,
    ):
        """并行调用多个远程智能体。

        Args:
          requests: 调用请求列表。每项需包含：
            - agent_name: 远程智能体名称
            - message: 发送给该智能体的消息
            - file_path: （可选）要附加的本地文件路径
          tool_context: 工具上下文。
          max_concurrency: （可选）并发上限。为空或 <= 0 时不限制。

        Returns:
          按输入顺序返回每个调用结果，结构如下：
            - index: 原请求序号
            - agent_name: 智能体名称
            - success: 是否成功
            - result: 成功时的结果
            - error / error_type: 失败时错误信息
        """
        if not requests:
            return []

        semaphore = (
            asyncio.Semaphore(max_concurrency)
            if max_concurrency and max_concurrency > 0
            else None
        )

        async def _run_single(index: int, request: dict[str, Any]):
            agent_name = str(request.get('agent_name', '')).strip()
            message = str(request.get('message', '')).strip()
            file_path = request.get('file_path')

            if not agent_name:
                return {
                    'index': index,
                    'agent_name': '',
                    'success': False,
                    'error_type': 'ValueError',
                    'error': '请求缺少 agent_name',
                }
            if not message:
                return {
                    'index': index,
                    'agent_name': agent_name,
                    'success': False,
                    'error_type': 'ValueError',
                    'error': f'{agent_name} 的请求缺少 message',
                }

            async def _invoke():
                return await self._send_message_internal(
                    agent_name=agent_name,
                    message=message,
                    tool_context=tool_context,
                    file_path=file_path,
                    sync_legacy_state=False,
                )

            try:
                if semaphore:
                    async with semaphore:
                        result = await _invoke()
                else:
                    result = await _invoke()
                return {
                    'index': index,
                    'agent_name': agent_name,
                    'success': True,
                    'result': result,
                }
            except Exception as e:
                return {
                    'index': index,
                    'agent_name': agent_name,
                    'success': False,
                    'error_type': type(e).__name__,
                    'error': str(e),
                }

        results = await asyncio.gather(
            *[_run_single(idx, req) for idx, req in enumerate(requests)]
        )
        results.sort(key=lambda x: x['index'])

        # 保持“当前智能体”语义：使用最后一个成功调用的智能体更新状态。
        state = tool_context.state
        for item in reversed(results):
            if item.get('success'):
                agent_name = item['agent_name']
                self._sync_legacy_state(
                    state=state,
                    agent_name=agent_name,
                    session=self._get_agent_session(state, agent_name),
                )
                break

        return results

    async def _send_message_internal(
        self,
        agent_name: str,
        message: str,
        tool_context: ToolContext,
        file_path: Optional[str],
        sync_legacy_state: bool,
    ):
        # 前置验证
        if agent_name not in self.remote_agent_connections:
            raise ValueError(f'{agent_name}没有找到')

        async with self._get_agent_lock(agent_name):
            state = tool_context.state
            session = self._get_agent_session(state, agent_name)
            client = self.remote_agent_connections[agent_name]
            if not client:
                raise ValueError(f'{agent_name}A2A客户端不可用')

            attachment = await self._resolve_file_attachment(
                agent_name=agent_name,
                message=message,
                file_path=file_path,
                tool_context=tool_context,
            )
            request_message = self._build_request_message(
                message=message,
                context_id=session.get('context_id'),
                task_id=session.get('task_id'),
                attachment=attachment,
            )
            response = await self._send_with_retry(
                agent_name, client, request_message
            )
            result = await self._process_response(
                agent_name=agent_name,
                response=response,
                tool_context=tool_context,
                session=session,
            )
            if sync_legacy_state:
                self._sync_legacy_state(state, agent_name, session)
            return result

    def _build_request_message(
        self,
        message: str,
        context_id: Optional[str],
        task_id: Optional[str],
        attachment: FileWithBytes | None,
    ) -> Message:
        request_message = Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=message))],
            message_id=str(uuid.uuid4()),
            context_id=context_id,
            task_id=task_id,
        )

        if attachment is not None:
            request_message.parts.append(
                Part(
                    root=FilePart(
                        file=attachment
                    )
                )
            )
        return request_message

    async def _resolve_file_attachment(
        self,
        agent_name: str,
        message: str,
        file_path: Optional[str],
        tool_context: ToolContext,
    ) -> FileWithBytes | None:
        # 1) 显式 file_path 优先。
        if file_path and file_path.strip() != '':
            return self._load_attachment_from_path(file_path)

        # 2) 自动附件转发：仅对支持文件输入且消息看起来在谈“文件解析”的场景启用。
        if not self._should_auto_attach_from_artifacts(agent_name, message):
            return None

        try:
            artifact_names = await tool_context.list_artifacts()
        except Exception:
            return None
        if not artifact_names:
            return None

        # 优先最新 artifact。
        for artifact_name in reversed(artifact_names):
            try:
                artifact = await tool_context.load_artifact(artifact_name)
            except Exception:
                continue
            if attachment := self._attachment_from_artifact(
                artifact_name, artifact
            ):
                return attachment
        return None

    @staticmethod
    def _load_attachment_from_path(file_path: str) -> FileWithBytes:
        with open(file_path, 'rb') as f:
            raw = f.read()
        file_name = os.path.basename(file_path)
        mime_type, _ = mimetypes.guess_type(file_name)
        return FileWithBytes(
            name=file_name,
            bytes=base64.b64encode(raw).decode('utf-8'),
            mime_type=mime_type or 'application/octet-stream',
        )

    def _should_auto_attach_from_artifacts(
        self, agent_name: str, message: str
    ) -> bool:
        card = self.cards.get(agent_name)
        if not card:
            return False

        input_modes = set(card.default_input_modes or [])
        supports_binary = any(
            mode not in {'text', 'text/plain'} for mode in input_modes
        )
        if not supports_binary:
            return False

        lower_message = message.lower()
        file_keywords = (
            '文件',
            '文档',
            '附件',
            'pdf',
            'doc',
            'image',
            '图片',
            '解析',
        )
        return any(keyword in lower_message for keyword in file_keywords)

    @staticmethod
    def _attachment_from_artifact(
        artifact_name: str, artifact: types.Part | None
    ) -> FileWithBytes | None:
        if artifact is None:
            return None
        blob = artifact.inline_data
        if blob is None or blob.data is None:
            return None

        mime_type = blob.mime_type or 'application/octet-stream'
        # artifact 名称通常就是原始文件名；若无后缀则按 mime 补一个。
        file_name = artifact_name
        if '.' not in os.path.basename(file_name):
            ext = mimetypes.guess_extension(mime_type) or '.bin'
            file_name = f'{file_name}{ext}'

        return FileWithBytes(
            name=file_name,
            bytes=base64.b64encode(blob.data).decode('utf-8'),
            mime_type=mime_type,
        )

    async def _send_with_retry(
        self,
        agent_name: str,
        client: RemoteAgentConnections,
        request_message: Message,
    ):
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                return await client.send_message(request_message)
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    error_msg = (
                        f"与智能体 {agent_name} 通信失败，已尝试 {max_retries} 次重试。"
                        f"错误详情: {str(e)}"
                    )
                    print("----发送消息的时候出现了异常-----")
                    print(error_msg)
                    print(f"错误类型: {type(e).__name__}")
                    import traceback

                    traceback.print_exc()
                    return [
                        f"很抱歉，与代理 {agent_name} 的通信出现故障，"
                        "请稍后重试或联系管理员。"
                    ]

                wait_time = 2 ** retry_count
                print(
                    f"与代理 {agent_name} 通信失败，"
                    f"第 {retry_count} 次重试前等待 {wait_time} 秒..."
                )
                await asyncio.sleep(wait_time)

        return []

    async def _process_response(
        self,
        agent_name: str,
        response: Message | Task | list[str] | None,
        tool_context: ToolContext,
        session: dict[str, Any],
    ):
        if isinstance(response, list):
            return response

        if response is None:
            return [f'{agent_name} 返回空响应']

        if isinstance(response, Message):
            return await convert_parts(response.parts, tool_context)

        task: Task = response
        session['session_active'] = task.status.state not in [
            TaskState.completed,
            TaskState.canceled,
            TaskState.failed,
            TaskState.unknown,
        ]
        if task.context_id:
            session['context_id'] = task.context_id
        session['task_id'] = task.id

        if task.status.state == TaskState.input_required:
            tool_context.actions.skip_summarization = True
            tool_context.actions.escalate = True
        elif task.status.state == TaskState.canceled:
            return "任务取消,请稍后再试"
        elif task.status.state == TaskState.failed:
            raise ValueError(f'{agent_name} 任务 {task.id} 失败')

        response_parts = []
        session['task_id'] = None
        if task.status.message:
            if ts := self.timestamp_extension.get_timestamp(
                task.status.message
            ):
                response_parts.append(f'[at {ts.astimezone().isoformat()}]')
            response_parts.extend(
                await convert_parts(task.status.message.parts, tool_context)
            )
        if task.artifacts:
            for artifact in task.artifacts:
                if ts := self.timestamp_extension.get_timestamp(artifact):
                    response_parts.append(f'[at {ts.astimezone().isoformat()}]')
                response_parts.extend(
                    await convert_parts(artifact.parts, tool_context)
                )
        return response_parts

    def _ensure_session_map(self, state: dict[str, Any]) -> dict[str, Any]:
        sessions = state.get(self.AGENT_SESSIONS_KEY)
        if not isinstance(sessions, dict):
            sessions = {}
            state[self.AGENT_SESSIONS_KEY] = sessions
        return sessions

    def _get_agent_session(
        self, state: dict[str, Any], agent_name: str
    ) -> dict[str, Any]:
        sessions = self._ensure_session_map(state)
        session = sessions.get(agent_name)
        if not isinstance(session, dict):
            session = {
                'context_id': None,
                'task_id': None,
                'session_active': False,
            }
            sessions[agent_name] = session
        return session

    def _sync_legacy_state(
        self,
        state: dict[str, Any],
        agent_name: str,
        session: dict[str, Any],
    ) -> None:
        state['agent'] = agent_name
        state['context_id'] = session.get('context_id')
        state['task_id'] = session.get('task_id')
        state['session_active'] = session.get('session_active', False)

    def _get_agent_lock(self, agent_name: str) -> asyncio.Lock:
        lock = self._agent_locks.get(agent_name)
        if lock is None:
            lock = asyncio.Lock()
            self._agent_locks[agent_name] = lock
        return lock

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
