"""数据模型：知识点 与 学习记录。"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _today() -> str:
    return date.today().isoformat()


@dataclass
class KnowledgePoint:
    """一个知识点：名称 + 原理讲解 + 可视化（链接或文字说明）。"""

    id: Optional[int]
    name: str
    category: str
    principle: str                      # 原理讲解（纯文本，空行分段）
    visualization: str = ""             # 可视化：http(s) 链接 或 文字说明
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "KnowledgePoint":
        tags = (row["tags"] or "").split(",") if "tags" in row.keys() else []
        return cls(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            principle=row["principle"],
            visualization=row["visualization"] or "",
            tags=[t.strip() for t in tags if t.strip()],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "principle": self.principle,
            "visualization": self.visualization,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class LearningRecord:
    """知识点上的学习标注：掌握度、复习次数与下次复习时间。

    「未标注」= 没有对应记录行；一旦标记学习即产生本记录。
    """

    id: Optional[int]
    point_id: int
    status: str = "learning"            # learning | mastered
    mastery: int = 1                    # 1~5
    review_count: int = 0
    last_reviewed_at: str = field(default_factory=_now)
    next_review_at: str = field(default_factory=_today)  # YYYY-MM-DD
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "LearningRecord":
        return cls(
            id=row["id"],
            point_id=row["point_id"],
            status=row["status"],
            mastery=row["mastery"],
            review_count=row["review_count"],
            last_reviewed_at=row["last_reviewed_at"],
            next_review_at=row["next_review_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "point_id": self.point_id,
            "status": self.status,
            "mastery": self.mastery,
            "review_count": self.review_count,
            "last_reviewed_at": self.last_reviewed_at,
            "next_review_at": self.next_review_at,
            "is_due": self.next_review_at <= _today(),
        }
