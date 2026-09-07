"""复习与掌握度更新逻辑（SRS-lite：简化版间隔重复）。

规则：
- 自评三档：forgot（忘了）/ fuzzy（模糊）/ solid（记得）。
- forgot: 掌握度 -1（不低于 1），明天再复习；
- fuzzy : 掌握度不变，按当前掌握度的基准间隔再约一次；
- solid : 掌握度 +1（不超过 5），按新掌握度的更长间隔安排。
- 掌握度 >= MASTERED_AT(4) 时状态标记为「已掌握」，但仍在复习队列中巩固。
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta

from . import config
from .models import LearningRecord

RATING_FORGOT = "forgot"
RATING_FUZZY = "fuzzy"
RATING_SOLID = "solid"
RATINGS = (RATING_FORGOT, RATING_FUZZY, RATING_SOLID)
RATING_LABELS = {RATING_FORGOT: "忘了", RATING_FUZZY: "模糊", RATING_SOLID: "记得"}

# 各掌握度对应的基准复习间隔（天）
BASE_INTERVAL_DAYS = {1: 1, 2: 2, 3: 5, 4: 8, 5: 15}


def _today() -> date:
    return date.today()


def next_interval_days(mastery: int, rating: str) -> int:
    """根据（更新后的）掌握度与自评结果计算下一次复习间隔。"""
    if rating == RATING_FORGOT:
        return 1
    return BASE_INTERVAL_DAYS.get(max(config.MASTERY_MIN, min(config.MASTERY_MAX, mastery)), 2)


def apply_rating(record: LearningRecord, rating: str) -> LearningRecord:
    """把一次自评应用到学习记录上，返回更新后的记录（不落库）。

    Raises:
        ValueError: rating 不合法。
    """
    if rating not in RATINGS:
        raise ValueError(f"非法的自评结果: {rating!r}，可选: {', '.join(RATINGS)}")

    delta = {RATING_FORGOT: -1, RATING_FUZZY: 0, RATING_SOLID: 1}[rating]
    new_mastery = max(config.MASTERY_MIN, min(config.MASTERY_MAX, record.mastery + delta))
    interval = next_interval_days(new_mastery, rating)
    now = datetime.now().isoformat(timespec="seconds")

    return replace(
        record,
        mastery=new_mastery,
        review_count=record.review_count + 1,
        status=config.STATUS_MASTERED if new_mastery >= config.MASTERED_AT else config.STATUS_LEARNING,
        last_reviewed_at=now,
        next_review_at=(_today() + timedelta(days=interval)).isoformat(),
        updated_at=now,
    )
