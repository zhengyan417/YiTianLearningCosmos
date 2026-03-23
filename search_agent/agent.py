import os
import dotenv
import re
from urllib.parse import quote
import logging

from collections.abc import AsyncIterable
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents.structured_output import ToolStrategy
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel
from langchain_core.messages import AIMessage, ToolMessage
from typing import Literal, Any
from langchain_openai import ChatOpenAI
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.checkpoint.memory import InMemorySaver
import httpx

dotenv.load_dotenv()
logger = logging.getLogger(__name__)


def _extract_city_from_query(query: str) -> str:
    """从中文天气查询中提取城市名，提取失败时返回北京。"""
    q = query.strip()
    patterns = [
        r'查询一下(.+?)的天气',
        r'(.+?)天气',
        r'(.+?)今天天气',
        r'(.+?)明天天气',
    ]
    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            city = match.group(1).strip(' ，,。！？?')
            city = city.replace('帮我', '').replace('请', '').strip()
            if city:
                return city
    return '北京'


def _weather_lookup(query: str) -> str:
    """使用 wttr.in 查询天气（免 key）。"""
    city = _extract_city_from_query(query)
    url = f'https://wttr.in/{quote(city)}'
    params = {'format': 'j1', 'lang': 'zh'}
    try:
        response = httpx.get(url, params=params, timeout=12.0)
        response.raise_for_status()
        data = response.json()

        current = (data.get('current_condition') or [{}])[0]
        nearest = (data.get('nearest_area') or [{}])[0]
        area_name = (
            (nearest.get('areaName') or [{}])[0].get('value')
            or city
        )
        weather_desc = (
            (current.get('lang_zh') or [{}])[0].get('value')
            or (current.get('weatherDesc') or [{}])[0].get('value')
            or '未知'
        )
        temp_c = current.get('temp_C', 'N/A')
        feels_like = current.get('FeelsLikeC', 'N/A')
        humidity = current.get('humidity', 'N/A')
        wind = current.get('windspeedKmph', 'N/A')

        return (
            f'{area_name} 当前天气：{weather_desc}，气温 {temp_c}°C，'
            f'体感 {feels_like}°C，湿度 {humidity}%，风速 {wind} km/h。'
        )
    except Exception as e:
        return f'天气查询失败（{city}）：{str(e)}'


@tool(parse_docstring=True)
def query_weather(query: str) -> str:
    """查询天气信息（免 API key）。

    Args:
        query: 天气查询语句，例如“帮我查询一下北京的天气”

    Returns:
        当前天气的可读文本
    """
    return _weather_lookup(query)


@tool(parse_docstring=True)
def web_search_fallback(query: str, max_results: int = 5) -> str:
    """当 MCP 工具不可用时的网页搜索兜底工具。

    Args:
        query: 搜索关键词
        max_results: 最多返回条数

    Returns:
        搜索结果摘要文本
    """
    params = {
        'q': query,
        'format': 'json',
        'no_html': 1,
        'skip_disambig': 1,
    }
    try:
        response = httpx.get(
            'https://api.duckduckgo.com/',
            params=params,
            timeout=12.0,
        )
        response.raise_for_status()
        payload = response.json()

        items = []
        abstract = payload.get('AbstractText')
        if abstract:
            items.append(
                {
                    'title': payload.get('Heading') or query,
                    'url': payload.get('AbstractURL') or '',
                    'snippet': abstract,
                }
            )

        related = payload.get('RelatedTopics') or []
        for topic in related:
            if len(items) >= max_results:
                break
            if isinstance(topic, dict) and 'Text' in topic:
                items.append(
                    {
                        'title': topic.get('Text', '').split(' - ')[0],
                        'url': topic.get('FirstURL', ''),
                        'snippet': topic.get('Text', ''),
                    }
                )
            elif isinstance(topic, dict) and 'Topics' in topic:
                for sub in topic.get('Topics', []):
                    if len(items) >= max_results:
                        break
                    if isinstance(sub, dict) and 'Text' in sub:
                        items.append(
                            {
                                'title': sub.get('Text', '').split(' - ')[0],
                                'url': sub.get('FirstURL', ''),
                                'snippet': sub.get('Text', ''),
                            }
                        )

        if not items:
            return f'未检索到“{query}”的有效结果。'

        lines = [f'查询“{query}”的结果：']
        for idx, item in enumerate(items[:max_results], start=1):
            lines.append(
                f'{idx}. {item["title"]}\n链接: {item["url"]}\n摘要: {item["snippet"]}'
            )
        return '\n\n'.join(lines)
    except Exception as e:
        return f'搜索兜底工具执行失败：{str(e)}'

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
                timeout=120,
            )

        tools = [query_weather, web_search_fallback]
        tools.extend(self._load_mcp_tools())

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

    def _load_mcp_tools(self):
        """尝试加载 MCP 工具，失败时自动降级。"""
        enable_mcp_client = (
            os.getenv('ENABLE_SEARCH_MCP_CLIENT', 'false').lower() == 'true'
        )
        if not enable_mcp_client:
            return []

        mcp_url = os.getenv('MCP_SEARCH_SERVER_URL', 'http://127.0.0.1:8004/mcp')
        mcp_client = MultiServerMCPClient(
            {
                "search_server": {
                    "url": mcp_url,
                    "transport": "streamable_http",
                }
            }
        )

        import asyncio
        try:
            try:
                loop = asyncio.get_running_loop()
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, mcp_client.get_tools())
                    return future.result(timeout=10)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                tools = loop.run_until_complete(mcp_client.get_tools())
                loop.close()
                return tools
        except Exception as e:
            logger.warning(f"无法连接到MCP服务器({mcp_url}): {e}")
            return []

    @staticmethod
    def _is_weather_query(query: str) -> bool:
        keywords = ('天气', '温度', '下雨', '降雨', '气温')
        return any(k in query for k in keywords)

    # 2. 定义信息处理方法
    async def stream(self, query, context_id) -> AsyncIterable[dict[str, Any]]:
        # 天气查询优先走本地稳定链路，避免外部 MCP 不可用导致失败。
        if self._is_weather_query(query):
            yield {
                'is_task_complete': False,
                'require_user_input': False,
                'content': '正在查询天气信息...',
            }
            yield {
                'is_task_complete': True,
                'require_user_input': False,
                'content': _weather_lookup(query),
            }
            return

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
