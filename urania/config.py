"""Urania 全局配置。

所有路径默认相对项目根目录解析（而不是当前工作目录），
保证从任意位置（如打包成 .app 后双击运行）都能正确定位资源。
"""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Urania"
APP_VERSION = "0.1.0"

# 路径 ----------------------------------------------------------------------
PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
DATA_DIR = Path(os.environ.get("URANIA_DATA_DIR", PROJECT_ROOT / "data"))
DB_PATH = Path(os.environ.get("URANIA_DB", DATA_DIR / "urania.db"))
SEED_FILE = DATA_DIR / "seed_knowledge.json"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# 网络 ----------------------------------------------------------------------
DEFAULT_HOST = "127.0.0.1"          # 仅本机访问，不暴露到局域网
DEFAULT_PORT = int(os.environ.get("URANIA_PORT", "8765"))

# 领域常量 ------------------------------------------------------------------
# 掌握程度：0 未学习；1~5 由低到高
MASTERY_MAX = 5
MASTERY_MIN = 1
MASTERY_LABELS = {
    0: "未学习",
    1: "初识 · 听说过",
    2: "理解 · 能复述",
    3: "熟悉 · 能解释",
    4: "掌握 · 能应用",
    5: "精通 · 能讲解",
}

# 学习状态机：unlearned --标记学习--> learning --mastery>=4--> mastered
STATUS_UNLEARNED = "unlearned"
STATUS_LEARNING = "learning"
STATUS_MASTERED = "mastered"
STATUS_LABELS = {
    STATUS_UNLEARNED: "未学习",
    STATUS_LEARNING: "学习中",
    STATUS_MASTERED: "已掌握",
}
# mastery 达到该值即视为「已掌握」
MASTERED_AT = 4

# 知识点默认分类（种子数据 / 前端新建知识点时使用）
DEFAULT_CATEGORIES = [
    "Python 基础",
    "Python 进阶",
    "AI / 机器学习",
    "深度学习",
    "工程实践",
]
