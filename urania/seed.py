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
    """按名称幂等导入种子数据；数据库为空或部分缺失时自动补齐。

    Returns:
        本次新增的知识点数量。
    """
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
