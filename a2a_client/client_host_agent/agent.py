import os
import warnings
warnings.filterwarnings("ignore")
from dotenv import load_dotenv

import sys
from pathlib import Path

# 防御性注入项目根：始终以当前文件定位，避免 ADK 切换 cwd 失去 core 包
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # …/YiTianLearningCosmos
PROJECT_ROOT_UP = PROJECT_ROOT.parent               # …/Projects（兜底）
for candidate in (PROJECT_ROOT, PROJECT_ROOT_UP):
    c = str(candidate)
    if c not in sys.path:
        sys.path.insert(0, c)

import core.bootstrap  # 确保项目根路径在 sys.path
from core.settings import settings
from core.async_utils import create_http_client

from .host_agent import HostAgent

# 补充防御性路径注入（ADK 可能以不同 cwd 加载）
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv() # 加载环境变量

http_client = create_http_client()  # 统一超时与代理关闭，避免 VPN 影响本地

root_agent = HostAgent(
    [
        settings.FILE_PARSE_AGENT_URL,
        settings.CODE_AGENT_URL,
        settings.RAG_AGENT_URL,
        settings.SEARCH_AGENT_URL,
        settings.RESEARCH_AGENT_URL,
    ],
    http_client=http_client,
).create_agent()
