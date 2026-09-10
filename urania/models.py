"""数据模型：知识点 与 学习记录。"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _today() -> str:
    return date.today().isoformat()


def _opt(row: sqlite3.Row, key: str, default=""):
    """读取可能不存在的列（老库升级过程中的兼容手段）。

    注意：``sqlite3.Row`` 的 ``in`` 迭代的是**值**而不是列名，
    所以必须写 ``in row.keys()``——ruff 的 SIM118 建议在这里是错的。
    """
    return row[key] if key in row.keys() else default  # noqa: SIM118


@dataclass
class KnowledgePoint:
    """一个知识点。

    ``principle`` 是「一整段原理讲解」的原始字段（手写条目用）；
    下面的四段式字段来自 Mnemosyne 知识库，均为空时前端回退到 principle。
    """

    id: int | None
    name: str
    category: str
    principle: str                      # 原理讲解（纯文本，空行分段）
    visualization: str = ""             # 可视化：http(s) 链接 或 文字说明
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    # ---- 四段式结构 ----
    definition: str = ""                # ① 一句话定义
    mechanism: str = ""                 # ② 原理机制
    key_point: str = ""                 # ③ 面试/实战要点
    code_example: str = ""              # ④ 代码例子（markdown 围栏，可拷贝）
    # ---- 学习元信息 ----
    source: str = ""                    # 出处锚点（如 Python-100-Days Day17）
    self_test: str = ""                 # 自测关卡
    module: str = ""                    # 模块码（如 M04）
    stage: int = 1                      # 阶段 1 / 2
    difficulty: int = 0                 # 1~5；0 表示未标定

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> KnowledgePoint:
        tags = (row["tags"] or "").split(",") if "tags" in row.keys() else []  # noqa: SIM118
        return cls(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            principle=row["principle"],
            visualization=row["visualization"] or "",
            tags=[t.strip() for t in tags if t.strip()],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            definition=_opt(row, "definition"),
            mechanism=_opt(row, "mechanism"),
            key_point=_opt(row, "key_point"),
            code_example=_opt(row, "code_example"),
            source=_opt(row, "source"),
            self_test=_opt(row, "self_test"),
            module=_opt(row, "module"),
            stage=_opt(row, "stage", 1) or 1,
            difficulty=_opt(row, "difficulty", 0) or 0,
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
            "definition": self.definition,
            "mechanism": self.mechanism,
            "key_point": self.key_point,
            "code_example": self.code_example,
            "source": self.source,
            "self_test": self.self_test,
            "module": self.module,
            "stage": self.stage,
            "difficulty": self.difficulty,
        }


@dataclass
class LearningRecord:
    """知识点上的学习标注：掌握度、复习次数与下次复习时间。

    「未标注」= 没有对应记录行；一旦标记学习即产生本记录。
    """

    id: int | None
    point_id: int
    status: str = "learning"            # learning | mastered
    mastery: int = 1                    # 1~5
    review_count: int = 0
    last_reviewed_at: str = field(default_factory=_now)
    next_review_at: str = field(default_factory=_today)  # YYYY-MM-DD
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> LearningRecord:
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


# 事件来源：标记学习 / 复习自评
SOURCE_LEARN = "learn"
SOURCE_REVIEW = "review"


@dataclass
class ReviewLog:
    """一次学习或复习事件的只追加记录（对标 Anki 的 revlog）。

    ``learning_records`` 存「当前状态」（每点一行、会被覆盖），本模型对应
    「历史事件」（每次追加一行、永不修改）。两者分离后才能真正统计遗忘曲线、
    真实保留率，并为将来的调度算法调优保留原始数据。
    """

    id: int | None
    point_id: int
    source: str                        # learn | review
    rating: str | None              # forgot | fuzzy | solid；标记学习时为 None
    reviewed_at: str
    elapsed_days: int | None        # 距上次复习的天数；首次为 None
    scheduled_days: int | None      # 本次安排的下次间隔天数
    prev_mastery: int | None        # 变更前掌握度；首次为 None
    new_mastery: int
    created_at: str = field(default_factory=_now)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ReviewLog:
        return cls(
            id=row["id"],
            point_id=row["point_id"],
            source=row["source"],
            rating=row["rating"],
            reviewed_at=row["reviewed_at"],
            elapsed_days=row["elapsed_days"],
            scheduled_days=row["scheduled_days"],
            prev_mastery=row["prev_mastery"],
            new_mastery=row["new_mastery"],
            created_at=row["created_at"],
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "point_id": self.point_id,
            "source": self.source,
            "rating": self.rating,
            "reviewed_at": self.reviewed_at,
            "elapsed_days": self.elapsed_days,
            "scheduled_days": self.scheduled_days,
            "prev_mastery": self.prev_mastery,
            "new_mastery": self.new_mastery,
            "created_at": self.created_at,
        }
