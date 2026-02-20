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

class CodeAgent:
    system_prompt = """
你是一个专业的 Python 代码生成器。用户会提供一个明确的编程需求。你的任务是仅输出可直接运行的 Python 代码，满足该需求。  
你必须只输出可运行的 Python 代码，不要任何解释、注释、Markdown 或额外文本。
不要输出python，不要说‘好的’，直接输出代码。
严格遵守以下规则：  
1. 不要输出任何解释、说明、注释或 Markdown（如 ）。  
2. 不要包含示例用法、测试代码或 print 语句（除非需求明确要求）。  
3. 只输出代码本身，且代码必须语法正确、可直接执行。  
4. 如果需求模糊，请基于最常见场景实现合理功能。  

现在，请根据以下需求生成代码：

使用示例（你只需把“需求”部分替换即可）：
需求：写一个函数，接收一个列表，返回其中所有偶数的平方。

智能体应输出：
python
def square_evens(lst):
    return [x**2 for x in lst if x % 2 == 0]

注意：实际输出中没有 python 包裹，也没有任何额外文字。
 """

    format_instruction = """
        如果你需要提供更多的信息来完成请求，设置status为"input_required"
        如果在处理请求的时候出现了错误，设置status为"error"
        如果你完成了规划智能体的请求，设置status为"input_required"
    """

    # 1.配置智能体
    def __init__(self, use_minimind=False):
        if use_minimind:
            llm = ChatOpenAI(
                model='minimind',
                temperature=0.8,
                api_key="",
                base_url="http://localhost:8998/v1",
            )
        else:
            llm = ChatOpenAI(
                    model='deepseek-chat',
                    temperature=0.8,
                    api_key=os.getenv("DEEPSEEK_API_KEY"),
                    base_url=os.getenv("DEEPSEEK_BASE_URL"),
                )
        self.agent = create_agent(
            model=llm,
            system_prompt=self.system_prompt + self.format_instruction,
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
                    'content': '正在准备工作...'
                }
            # tool正在执行
            elif isinstance(message, ToolMessage):
                yield {
                    'is_task_complete': False,
                    'require_user_input': False,
                    'content': '正在工作中...'
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
                '无法处理，请稍后再试'
            ),
        }

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']