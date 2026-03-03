import os
from typing import Any, AsyncIterable
from datetime import datetime

# from daytona import Daytona
from deepagents import create_deep_agent
from langchain_deepseek import ChatDeepSeek
from deepagents.backends import FilesystemBackend # 文件后端
# from langchain_daytona import DaytonaSandbox

from research_agent_utils.prompts import (
    RESEARCHER_INSTRUCTIONS,
    RESEARCH_WORKFLOW_INSTRUCTIONS,
    SUBAGENT_DELEGATION_INSTRUCTIONS,
)
from research_agent_utils.tools import tavily_search, think_tool

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

        # 创建沙盒和后端
        research_root_dir = os.getenv("RESEARCH_FILE_PATH")
        os.makedirs(research_root_dir, exist_ok=True)
        backend = FilesystemBackend(root_dir=research_root_dir, virtual_mode=True)

        # Create the agent
        self.agent = create_deep_agent(
            model=model,
            tools=[tavily_search, think_tool],
            system_prompt=INSTRUCTIONS,
            subagents=[research_sub_agent],
            backend=backend
        )
    
    async def stream(self, query, context_id):
        # 调用底层 agent 的 stream 方法（它是同步的）
        for namespace, chunk in self.agent.stream(
            {"messages": [{"role": "user", "content": query}]},
            stream_mode="updates",
            subgraphs=True,  
        ):
            if namespace:
                # Subagent event — namespace identifies the source
                print(f"[subagent: {namespace}]")
            else:
                # Main agent event
                print("[main agent]")
            print(chunk)
        
        # 任务完成，读取最终报告并 yield 结果
        with open(os.path.join(research_root_dir, f"final_report.md"), "r") as f:
            content = f.read()
        
        yield {
            'is_task_complete': True,
            'require_user_input': False,
            'content': content,
        }
      

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

if __name__ == "__main__":
    import asyncio
    
    async def main():
        research_agent = ResearchAgent()
        result = await research_agent.stream("研究一下 A2A 协议与 MCP 协议的关系", "test_context_id")
        print(result)
    
    asyncio.run(main())
