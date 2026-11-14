# -*- coding: utf-8 -*-
"""pytest 配置：确保 main 模块可被导入"""

import sys
from pathlib import Path

# 将 backend 目录加入 sys.path，使 tests 可直接 `from main import app`
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
