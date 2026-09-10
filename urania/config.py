"""Urania 全局配置。

两类路径严格区分（打包后尤其重要）：

- **只读资源**（`RESOURCE_ROOT`）：`frontend/`、种子数据。源码运行时在项目里；
  打包成 .app 后位于 bundle 的 `Contents/Resources`。
- **可写数据**（`DATA_DIR`）：数据库、备份、访问令牌、单实例锁。
  遵循 macOS 惯例放 `~/Library/Application Support/Urania`——
  应用包内部（尤其装进 /Applications 后）不可写。

旧版本把可写数据放在项目的 `data/` 下，首次启动会自动迁移（见 `db.migrate_legacy_data`）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Urania"
APP_VERSION = "0.1.0"

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent


def _resource_root() -> Path:
    """只读资源根目录（frontend/ 与种子数据）。"""
    if getattr(sys, "frozen", False):  # py2app / PyInstaller 打包后
        resource_path = os.environ.get("RESOURCEPATH")
        if resource_path:
            return Path(resource_path)
        return Path(sys.executable).resolve().parent.parent / "Resources"
    return PROJECT_ROOT


def _default_data_dir() -> Path:
    """默认可写数据目录（macOS 规范位置）。"""
    return Path.home() / "Library" / "Application Support" / APP_NAME


# 路径 ----------------------------------------------------------------------
RESOURCE_ROOT = _resource_root()

FRONTEND_DIR = RESOURCE_ROOT / "frontend"
SEED_FILE = RESOURCE_ROOT / "data" / "seed_knowledge.json"

DATA_DIR = Path(os.environ.get("URANIA_DATA_DIR", _default_data_dir()))
DB_PATH = Path(os.environ.get("URANIA_DB", DATA_DIR / "urania.db"))
BACKUP_DIR = Path(os.environ.get("URANIA_BACKUP_DIR", DATA_DIR / "backups"))
TOKEN_FILE = DATA_DIR / ".token"
LOCK_PATH = DATA_DIR / "urania.lock"

# 旧版运行数据位置：首次启动时自动搬到 DATA_DIR
LEGACY_DATA_DIR = PROJECT_ROOT / "data"

# 网络 ----------------------------------------------------------------------
DEFAULT_HOST = "127.0.0.1"          # 默认仅本机访问
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
