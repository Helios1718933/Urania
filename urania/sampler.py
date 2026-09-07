"""核心功能：随机抽取一个「未标注（未学习）」的知识点。

刻意保持纯函数：输入候选列表，输出被抽中的知识点，
随机性完全由 Python 标准库 random 提供，便于单元测试。
"""
from __future__ import annotations

import random
from typing import Optional, Sequence

from .models import KnowledgePoint


def draw_unlearned(
    candidates: Sequence[KnowledgePoint],
    rng: random.Random | None = None,
) -> Optional[KnowledgePoint]:
    """从候选（未学习）知识点中等概率随机抽取一个。

    Args:
        candidates: 未学习知识点列表（通常由 Repository.unlearned_points() 给出）。
        rng: 可注入的随机源，测试时用于固定种子；默认使用全局 random。

    Returns:
        被抽中的知识点；候选为空时返回 None（表示全部已进入学习循环）。
    """
    if not candidates:
        return None
    rng = rng or random
    return rng.choice(list(candidates))
