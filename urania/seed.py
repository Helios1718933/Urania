"""内置小数据库的种子数据导入（幂等，可重复执行）。"""
from __future__ import annotations

import json
import logging

from . import config
from .repository import KnowledgeRepository

logger = logging.getLogger(__name__)


def load_seed_file(path=config.SEED_FILE) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def seed_if_needed(repo: KnowledgeRepository, items: list[dict] | None = None) -> int:
    """**仅当知识库为空时**导入内置种子数据（首次安装的起步内容）。

    刻意不做「按名称补齐」：用户可能重命名过条目或导入过自己的知识库，
    每次启动补种会把旧名字的条目重新插回来，造成重复。

    Returns:
        本次新增的知识点数量；库非空时返回 0。
    """
    if repo.point_count() > 0:
        return 0

    if items is None:
        try:
            items = load_seed_file()
        except FileNotFoundError:
            logger.warning("种子数据文件不存在: %s", config.SEED_FILE)
            return 0
    inserted = repo.upsert_seed(items)
    if inserted:
        logger.info("种子数据已导入 %d 个知识点", inserted)
    return inserted
