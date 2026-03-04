import asyncio
import os
import sys
from pathlib import Path

# 确保项目根路径
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("ENABLE_A2A_MONITORING", "False")


def pytest_configure(config):
    # 全局事件循环策略，兼容 Windows
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
