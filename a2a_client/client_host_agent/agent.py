import os

from dotenv import load_dotenv

from .host_agent import HostAgent
from httpx import AsyncClient, Timeout

load_dotenv() # 加载环境变量

root_agent = HostAgent([ # 创建智能体
    os.getenv("FILE_PARSE_AGENT_URL"), # 文件解析智能体
    os.getenv("CODE_AGENT_URL"),
    os.getenv("DOCTOR_AGENT_URL"),
    ],
    http_client=AsyncClient(timeout=Timeout(300.0, connect=10.0))).create_agent() # 创建智能体