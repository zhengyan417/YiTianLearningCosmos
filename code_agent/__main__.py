import click
import uvicorn

import os, sys
from pathlib import Path
# 防御性注入项目根，避免从子目录运行找不到 core
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT_UP = PROJECT_ROOT.parent
for candidate in (PROJECT_ROOT, PROJECT_ROOT_UP):
    c = str(candidate)
    if c not in sys.path:
        sys.path.insert(0, c)

import core.bootstrap  # 统一项目根路径注入

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

from code_agent.agent import CodeAgent
from code_agent.agent_executor import CodeAgentExecutor

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
