import click
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    InMemoryTaskStore,
)
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from dotenv import load_dotenv
load_dotenv()

from agent import ResearchAgent
from agent_executor import ResearchAgentExecutor


@click.command() # 创建命令行接口
@click.option('--host', 'host', default='localhost') # 主机
@click.option('--port', 'port', default=10005) # 端口
def main(host, port):
    # 1. 定义AgentSkill
    research_skill = AgentSkill(
        id='research_tool',
        name='研究工具',
        description='根据用户要求进行研究',
        tags=['search'],
        examples=[r'帮我研究一下A2A与MCP的关系', r"研究一下量子计算"]
    )
    # 2. 定义AgentCard
    agent_card = AgentCard(
        name='研究智能体',
        description='根据用户要求进行研究(包含网络搜索功能)',
        url=f'http://{host}:{port}/',
        version='1.0.0',
        default_input_modes=ResearchAgent.SUPPORTED_CONTENT_TYPES,
        default_output_modes=ResearchAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=AgentCapabilities(streaming=True, push_notifications=True),
        skills=[research_skill],
    )

    # 3. 配置服务器
    request_handler = DefaultRequestHandler(
        agent_executor=ResearchAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,http_handler=request_handler
    )

    # 4. 启动服务器
    uvicorn.run(server.build(), host=host, port=port)

if __name__ == "__main__":
    main()