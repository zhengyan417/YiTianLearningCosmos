import os
from typing import Any, AsyncIterable
from datetime import datetime

# from daytona import Daytona
from deepagents import create_deep_agent
from langchain_deepseek import ChatDeepSeek
from deepagents.backends import FilesystemBackend # 文件后端
# from langchain_daytona import DaytonaSandbox

from research_agent.research_agent_utils.prompts import (
    RESEARCHER_INSTRUCTIONS,
    RESEARCH_WORKFLOW_INSTRUCTIONS,
    SUBAGENT_DELEGATION_INSTRUCTIONS,
)
from research_agent.research_agent_utils.tools import (
    tavily_search,
    think_tool,
    run_research_search,
)

# 加载环境变量
import dotenv
dotenv.load_dotenv()


class ResearchAgent:
    def __init__(
        self, 
        max_concurrent_research_units: int = 3, 
        max_researcher_iterations: int = 3
    ):
        # Get current date
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Combine orchestrator instructions (RESEARCHER_INSTRUCTIONS only for sub-agents)
        INSTRUCTIONS = (
            RESEARCH_WORKFLOW_INSTRUCTIONS
            + "\n\n"
            + "=" * 80
            + "\n\n"
            + SUBAGENT_DELEGATION_INSTRUCTIONS.format(
                max_concurrent_research_units=max_concurrent_research_units,
                max_researcher_iterations=max_researcher_iterations,
            )
        )

        # Create research sub-agent
        research_sub_agent = {
            "name": "research-agent",
            "description": "Delegate research to the sub-agent researcher. Only give this researcher one topic at a time.",
            "system_prompt": RESEARCHER_INSTRUCTIONS.format(date=current_date),
            "tools": [tavily_search, think_tool],
        }

        # 采用deepseek模型
        model = ChatDeepSeek(
            model="deepseek-chat",
            temperature=0.6,
            max_tokens=None,
            timeout=None,
            max_retries=2,
        )
        self.model = model

        # 创建沙盒和后端
        research_root_dir = os.getenv("RESEARCH_FILE_PATH")
        if not research_root_dir:
            research_root_dir = os.path.join(
                os.path.dirname(__file__),
                "backend",
            )
        os.makedirs(research_root_dir, exist_ok=True)
        self.research_root_dir = research_root_dir
        backend = FilesystemBackend(
            root_dir=self.research_root_dir,
            virtual_mode=True,
        )

        # Create the agent
        self.agent = create_deep_agent(
            model=model,
            tools=[tavily_search, think_tool],
            system_prompt=INSTRUCTIONS,
            subagents=[research_sub_agent],
            backend=backend
        )
    
    async def stream(self, query, context_id):
        # 默认走快速研究路径，优先保证稳定产出最终结果。
        quick_content = await self._quick_research(query)
        yield {
            'is_task_complete': True,
            'require_user_input': False,
            'content': quick_content,
        }
        return

    async def _quick_research(self, query: str) -> str:
        """快速研究：检索 + 一次性总结，避免长时间挂起。"""
        try:
            search_material = run_research_search(
                query=query,
                max_results=3,
                topic="general",
            )
            prompt = f"""
你是一名研究助理。请基于给定资料，生成一份简洁、结构化、可读的中文研究结论。

用户问题：
{query}

检索资料：
{search_material}

输出要求：
1. 先给出“结论摘要”（3-5条）。
2. 再给出“关键依据”（列点，包含来源链接）。
3. 最后给出“局限性与后续建议”。
"""
            response = self.model.invoke(prompt)
            content = (
                response.content
                if hasattr(response, 'content') and response.content
                else str(response)
            )

            final_report_path = os.path.join(self.research_root_dir, "final_report.md")
            with open(final_report_path, "w", encoding="utf-8") as f:
                f.write(content)
            return content
        except Exception as e:
            return (
                "研究流程执行时出现异常，已降级返回错误摘要：\n"
                f"{type(e).__name__}: {str(e)}"
            )
      

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

if __name__ == "__main__":
    import asyncio
    
    async def main():
        research_agent = ResearchAgent()
        async for result in research_agent.stream(
            "研究一下 A2A 协议与 MCP 协议的关系",
            "test_context_id",
        ):
            print(result)
    
    asyncio.run(main())
