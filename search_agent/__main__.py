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

from agent import SearchAgent
from agent_executor import SearchAgentExecutor


@click.command() # 创建命令行接口
@click.option('--host', 'host', default='localhost') # 主机
@click.option('--port', 'port', default=10004) # 端口
def main(host, port):
    # 1. 定义AgentSkill
    serach_skill = AgentSkill(
        id='search_information',
        name='查询工具',
        description='根据需求查询用户的个人信息或者进行网络搜索',
        tags=['search'],
        examples=[r'帮我查询一下北京的天气', r"查询一下用户的个人信息"]
    )
    # 2. 定义AgentCard
    agent_card = AgentCard(
        name='搜索智能体',
        description='根据需求查询用户的个人信息或者进行网络搜索',
        url=f'http://{host}:{port}/',
        version='1.0.0',
        default_input_modes=SearchAgent.SUPPORTED_CONTENT_TYPES,
        default_output_modes=SearchAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=AgentCapabilities(streaming=True, push_notifications=True),
        skills=[serach_skill],
    )

    # 3. 配置服务器
    request_handler = DefaultRequestHandler(
        agent_executor=SearchAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,http_handler=request_handler
    )

    # 4. 启动服务器
    uvicorn.run(server.build(), host=host, port=port)

if __name__ == "__main__":
    main()