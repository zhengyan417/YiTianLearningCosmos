import logging

import click

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from agent_executor import FileParseAgentExecutor
from agent import ParseAndChat

from dotenv import load_dotenv
load_dotenv() # 加载环境变量

logging.basicConfig(level=logging.INFO) # 设置日志级别
logger = logging.getLogger(__name__) # 创建日志记录器

@click.command() # 创建命令行接口
@click.option('--host', 'host', default='localhost') # 主机
@click.option('--port', 'port', default=10001) # 端口
def main(host, port): # 主函数
    """启动A2A服务器"""
    try:
        capabilities = AgentCapabilities( # 智能体能力
            streaming=True, push_notifications=True # 支持流失输出和推送通知
        )

        skill = AgentSkill( # 智能体技能
            id='parse_and_chat', # 技能ID
            name='文件解析和聊天', # 技能名称
            description='解析文件并且使用解析后的内容进行聊天', # 技能描述
            tags=['parse', 'chat', 'file', 'llama_parse'], # 技能标签
            examples=['这个文件讲了什么?'], # 技能示例
        )

        agent_card = AgentCard( # 智能体卡片
            name='文档解析智能体', # 智能体名称
            description='解析文件并且使用解析后的内容进行聊天', # 智能体描述
            url=f'http://{host}:{port}/', # 智能体URL
            version='1.0.0', # 智能体版本
            default_input_modes=FileParseAgentExecutor.SUPPORTED_INPUT_TYPES, # 智能体输入格式
            default_output_modes=FileParseAgentExecutor.SUPPORTED_OUTPUT_TYPES, # 智能体输出格式
            capabilities=capabilities, # 智能体能力
            skills=[skill], # 智能体技能
        )

        # httpx_client = httpx.AsyncClient()
        request_handler = DefaultRequestHandler( # 创建请求处理器
            agent_executor=FileParseAgentExecutor( # 创建智能体执行器
                agent=ParseAndChat(), # 创建智能体
            ),
            task_store=InMemoryTaskStore(), # 任务存储
            # push_notifier=InMemoryPushNotifier(httpx_client), 推送器
        )
        server = A2AStarletteApplication( # 创建Web服务器
            agent_card=agent_card, http_handler=request_handler # 智能体卡片,请求处理器
        )
        import uvicorn # 导入unicorn模块

        uvicorn.run(server.build(), host=host, port=port) # 运行服务器
    except Exception as e:
        logger.error(f'在服务器启动时出现错误: {e}') # 错误日志
        exit(1) # 退出


if __name__ == '__main__':
    main() # 运行主函数
