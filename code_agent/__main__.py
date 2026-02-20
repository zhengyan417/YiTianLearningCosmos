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

from agent import CodeAgent
from agent_executor import CodeAgentExecutor

load_dotenv()

@click.command() # 创建命令行接口
@click.option('--host', 'host', default='localhost') # 主机
@click.option('--port', 'port', default=10002) # 端口
def main(host, port):
    """启动CleverAgent Server"""
    # 1. 定义AgentSkill
    change_file_skill = AgentSkill(
        id='create_code',
        name='代码生成工具',
        description='根据需求生成特定的python代码',
        tags=['code'],
        examples=[r'帮我生成一段快速排序的代码']
    )
    # 2. 定义AgentCard
    agent_card = AgentCard(
        name='代码智能体',
        description='根据需求生成特定的python代码',
        url=f'http://{host}:{port}/',
        version='1.0.0',
        default_input_modes=CodeAgent.SUPPORTED_CONTENT_TYPES,
        default_output_modes=CodeAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=AgentCapabilities(streaming=True, push_notifications=True),
        skills=[change_file_skill],
    )

    # 3. 配置服务器
    request_handler = DefaultRequestHandler(
        agent_executor=CodeAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    server = A2AStarletteApplication(
        agent_card=agent_card,http_handler=request_handler
    )

    # 4. 启动服务器
    uvicorn.run(server.build(), host=host, port=port)

if __name__ == '__main__':
    main()
