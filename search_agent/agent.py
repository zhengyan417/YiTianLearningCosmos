import os
import dotenv

from collections.abc import AsyncIterable
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents.structured_output import ToolStrategy
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel
from langchain_core.messages import AIMessage, ToolMessage
from typing import Literal, Any
from langchain_openai import ChatOpenAI
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.checkpoint.memory import InMemorySaver

dotenv.load_dotenv()

class ResponseFormat(BaseModel):
    """规定返回给用户信息的格式"""

    status: Literal['input_required', 'completed', 'error'] = 'input_required'
    message: str

class SearchAgent:
    system_prompt = """
你是一个专业的搜索助手。你可以帮助用户进行以下操作：
1. 执行百度网络搜索
2. 查询用户的个人信息（学历、专业等）
3. 查看用户的查询历史记录

使用指南：
- 当用户需要搜索网络信息时，使用百度搜索工具
- 当用户询问个人信息时，直接查询用户档案
- 当用户想查看历史查询记录时，使用历史查询工具

重要提醒：
- 只要用户说明了，必须进行查询，不能要求用户重复说明
- 对于查询历史的请求，直接告知用户该功能需要相应工具支持
- 保持回答简洁明了，避免过度解释

请根据用户的具体需求选择合适的工具来完成任务。
"""

    format_instruction = """
        如果你需要提供更多的信息来完成请求，设置status为"input_required"
        如果在处理请求的时候出现了错误，设置status为"error"
        如果你完成了用户的请求，设置status为"completed"
    """

    # 1.配置智能体
    def __init__(self):
        llm = ChatOpenAI(
                model='deepseek-chat',
                temperature=0.8,
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url=os.getenv("DEEPSEEK_BASE_URL"),
            )
        
        # 创建MCP客户端连接到搜索服务器
        mcp_client = MultiServerMCPClient(
            {
                "search_server": {
                    "url": "http://localhost:8004",
                    "transport": "streamable_http",
                }
            }
        )
        
        # 异步获取工具
        import asyncio
        try:
            # 检查是否已有事件循环在运行
            try:
                loop = asyncio.get_running_loop()
                # 如果有运行中的循环，在另一个线程中执行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, mcp_client.get_tools())
                    tools = future.result(timeout=10)
            except RuntimeError:
                # 没有运行中的循环，创建新的
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                tools = loop.run_until_complete(mcp_client.get_tools())
                loop.close()
        except Exception as e:
            print(f"警告: 无法连接到MCP服务器: {e}")
            tools = []
        
        self.agent = create_agent(
            model=llm,
            system_prompt=self.system_prompt + self.format_instruction,
            tools=tools,
            middleware=[SummarizationMiddleware(
                model=llm,
                max_tokens_before_summary=4000,
                messages_to_keep=20,
            )],
            checkpointer=InMemorySaver(),
            response_format=ToolStrategy(ResponseFormat)
        )

    # 2. 定义信息处理方法
    async def stream(self, query, context_id) -> AsyncIterable[dict[str, Any]]:
        config : RunnableConfig = {'configurable' : {"thread_id" : context_id, "recursion_limit": 1000}}
        # 2.1 异步流式调用
        async for chunk in self.agent.astream(
                input={"messages": [{"role": "user", "content": query}]},
                config=config,
                stream_mode="values",
        ):
            message = chunk['messages'][-1]
            # agent尝试调用工具
            if isinstance(message, AIMessage) and message.tool_calls and len(message.tool_calls)>0 :
                yield{
                    'is_task_complete': False,
                    'require_user_input': False,
                    'content': '正在调用搜索工具...'
                }
            # tool正在执行
            elif isinstance(message, ToolMessage):
                yield {
                    'is_task_complete': False,
                    'require_user_input': False,
                    'content': '正在处理搜索结果...'
                }
        yield self.get_agent_response(config)


    # 再扩展定义agent回应的内容
    def get_agent_response(self, config):
        current_state = self.agent.get_state(config)   
        structured_response = current_state.values.get('structured_response')
        if structured_response and isinstance(structured_response, ResponseFormat):
            # 需要user的额外输入
            if structured_response.status == 'input_required':
                return {
                    'is_task_complete': False,
                    'require_user_input': True,
                    'content': structured_response.message,
                }
            # 出现错误
            if structured_response.status == 'error':
                return {
                    'is_task_complete': False,
                    'require_user_input': True,
                    'content': structured_response.message,
                }
            # 任务完成
            if structured_response.status == 'completed':
                return {
                    'is_task_complete': True,
                    'require_user_input': False,
                    'content': structured_response.message,
                }
        # 出现问题
        return {
            'is_task_complete': False,
            'require_user_input': True,
            'content': (
                '搜索处理失败，请稍后再试'
            ),
        }

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']