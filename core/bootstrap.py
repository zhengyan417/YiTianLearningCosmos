"""
bootstrap.py
-------------
确保在任何入口脚本中都能可靠地找到项目根路径与 `core` 包。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable


def ensure_project_root(markers: Iterable[str] = ("pyproject.toml", "README.md")) -> Path:
    """
    将项目根目录加入 sys.path，基于标记文件向上查找。
    若已存在则不重复添加。
    """
    cwd = Path(__file__).resolve().parent
    root = cwd
    while root != root.parent:
        if any((root / m).exists() for m in markers):
            break
        root = root.parent

    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


# 在模块导入时即执行，方便直接 `import core.bootstrap`
ensure_project_root()
