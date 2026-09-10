"""数据仓库：知识点与学习记录的读写（Repository 层）。

上层（API / 界面）只与本模块对话，不直接碰 SQL。
所有方法即用即提交，SQLite 单文件天然适合本应用的并发规模。
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from typing import Optional

from . import config
from .models import (
    SOURCE_LEARN,
    SOURCE_REVIEW,
    KnowledgePoint,
    LearningRecord,
    ReviewLog,
)
from .review import apply_rating


def _days_between(start_iso: str, end_iso: str) -> int:
    """两个 ISO 时间之间相差的天数（不足一天按 0 计）。"""
    start = datetime.fromisoformat(start_iso)
    end = datetime.fromisoformat(end_iso)
    return max(0, (end.date() - start.date()).days)


class RepositoryError(Exception):
    """业务错误（如知识点不存在、重名），API 层会转成 4xx。"""


class KnowledgeRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ------------------------------------------------------------- 知识点 --
    def list_points(self, category: Optional[str] = None) -> list[KnowledgePoint]:
        sql = "SELECT * FROM knowledge_points"
        params: tuple = ()
        if category:
            sql += " WHERE category = ?"
            params = (category,)
        sql += " ORDER BY category, id"
        return [KnowledgePoint.from_row(r) for r in self.conn.execute(sql, params)]

    def get_point(self, point_id: int) -> KnowledgePoint:
        row = self.conn.execute(
            "SELECT * FROM knowledge_points WHERE id = ?", (point_id,)
        ).fetchone()
        if row is None:
            raise RepositoryError(f"知识点不存在: {point_id}")
        return KnowledgePoint.from_row(row)

    def add_point(
        self,
        name: str,
        category: str,
        principle: str = "",
        visualization: str = "",
        tags: Optional[list[str]] = None,
    ) -> KnowledgePoint:
        """新增知识点。重名会抛 RepositoryError。"""
        if not name.strip():
            raise RepositoryError("知识点名称不能为空")
        now = date.today().isoformat()
        try:
            cur = self.conn.execute(
                "INSERT INTO knowledge_points (name, category, principle, visualization, tags,"
                " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name.strip(), category.strip(), principle.strip(), visualization.strip(),
                 ",".join(t.strip() for t in (tags or []) if t.strip()), now, now),
            )
        except sqlite3.IntegrityError:
            raise RepositoryError(f"知识点已存在: {name.strip()}")
        self.conn.commit()
        return self.get_point(cur.lastrowid)

    def upsert_seed(self, items: list[dict]) -> int:
        """按名称幂等导入种子数据，返回新增条数（不覆盖已有内容）。"""
        inserted = 0
        now = date.today().isoformat()
        for it in items:
            try:
                self.conn.execute(
                    "INSERT INTO knowledge_points (name, category, principle, visualization,"
                    " tags, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (it["name"], it.get("category", "未分类"), it.get("principle", ""),
                     it.get("visualization", ""), ",".join(it.get("tags", [])), now, now),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                continue  # 已存在，跳过
        self.conn.commit()
        return inserted

    # ------------------------------------------------------------- 学习记录 --
    def get_record(self, point_id: int) -> Optional[LearningRecord]:
        row = self.conn.execute(
            "SELECT * FROM learning_records WHERE point_id = ?", (point_id,)
        ).fetchone()
        return LearningRecord.from_row(row) if row else None

    def unlearned_points(self) -> list[KnowledgePoint]:
        """所有「未标注」知识点：没有学习记录的那些。"""
        rows = self.conn.execute(
            "SELECT p.* FROM knowledge_points p"
            " LEFT JOIN learning_records r ON r.point_id = p.id"
            " WHERE r.id IS NULL ORDER BY p.id"
        ).fetchall()
        return [KnowledgePoint.from_row(r) for r in rows]

    def learned_with_records(self) -> list[tuple[KnowledgePoint, LearningRecord]]:
        rows = self.conn.execute(
            "SELECT p.* FROM knowledge_points p"
            " JOIN learning_records r ON r.point_id = p.id"
            " ORDER BY r.next_review_at, r.mastery, r.last_reviewed_at"
        ).fetchall()
        return [(KnowledgePoint.from_row(r), self.get_record(r["id"])) for r in rows]

    def mark_learned(self, point_id: int, initial_mastery: int) -> LearningRecord:
        """把知识点标记为已学习：同一事务写入学习记录 + 追加首条日志。

        initial_mastery 取 1~3（越界自动收敛）。
        """
        self.get_point(point_id)  # 不存在则抛错
        initial_mastery = max(config.MASTERY_MIN, min(3, int(initial_mastery)))
        if self.get_record(point_id) is not None:
            raise RepositoryError(f"该知识点已在学习循环中: {point_id}")

        record = LearningRecord(
            id=None, point_id=point_id, mastery=initial_mastery,
            next_review_at=date.today().isoformat(),
        )
        with self.conn:  # 事务：记录与日志要么都写入，要么都回滚
            self._save(record)
            self._log_review(
                point_id=point_id,
                source=SOURCE_LEARN,
                rating=None,
                reviewed_at=record.last_reviewed_at,
                elapsed_days=None,
                scheduled_days=0,
                prev_mastery=None,
                new_mastery=initial_mastery,
            )
        saved = self.get_record(point_id)
        if saved is None:  # 刚提交，理论上不可达
            raise RepositoryError(f"学习记录写入后读取失败: {point_id}")
        return saved

    def apply_review(self, point_id: int, rating: str) -> LearningRecord:
        """应用一次复习自评：同一事务内完成「读 → 算 → 写记录 + 日志」。

        读-改-写收在事务里，避免并发请求下丢失更新（旧实现分三步、无事务）。
        """
        prev = self.get_record(point_id)
        if prev is None:
            raise RepositoryError(f"学习记录不存在: {point_id}")

        updated = apply_rating(prev, rating)  # 纯函数，见 review.py
        scheduled_days = (date.fromisoformat(updated.next_review_at) - date.today()).days

        with self.conn:
            self._save(updated)
            self._log_review(
                point_id=point_id,
                source=SOURCE_REVIEW,
                rating=rating,
                reviewed_at=updated.last_reviewed_at,
                elapsed_days=_days_between(prev.last_reviewed_at, updated.last_reviewed_at),
                scheduled_days=scheduled_days,
                prev_mastery=prev.mastery,
                new_mastery=updated.mastery,
            )
        saved = self.get_record(point_id)
        if saved is None:  # 刚提交，理论上不可达
            raise RepositoryError(f"学习记录更新后读取失败: {point_id}")
        return saved

    def reset_point(self, point_id: int) -> None:
        """删除学习记录，让知识点回到「未标注 / 未学习」状态。

        review_logs 中的历史不受影响（外键指向知识点而非学习记录），
        因此重置不会抹掉已经积累的复习历史。
        """
        self.conn.execute("DELETE FROM learning_records WHERE point_id = ?", (point_id,))
        self.conn.commit()

    def _save(self, record: LearningRecord) -> None:
        """写入学习记录（不提交；事务由调用方控制）。"""
        self.conn.execute(
            "INSERT INTO learning_records (point_id, status, mastery, review_count,"
            " last_reviewed_at, next_review_at, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(point_id) DO UPDATE SET status=excluded.status,"
            " mastery=excluded.mastery, review_count=excluded.review_count,"
            " last_reviewed_at=excluded.last_reviewed_at,"
            " next_review_at=excluded.next_review_at, updated_at=excluded.updated_at",
            (record.point_id, record.status, record.mastery, record.review_count,
             record.last_reviewed_at, record.next_review_at, record.created_at,
             record.updated_at),
        )

    def _log_review(
        self,
        point_id: int,
        source: str,
        rating: Optional[str],
        reviewed_at: str,
        elapsed_days: Optional[int],
        scheduled_days: Optional[int],
        prev_mastery: Optional[int],
        new_mastery: int,
    ) -> None:
        """追加一条复习日志（不提交；事务由调用方控制）。"""
        self.conn.execute(
            "INSERT INTO review_logs (point_id, source, rating, reviewed_at,"
            " elapsed_days, scheduled_days, prev_mastery, new_mastery, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (point_id, source, rating, reviewed_at, elapsed_days,
             scheduled_days, prev_mastery, new_mastery, reviewed_at),
        )

    # ------------------------------------------------------------- 复习日志 --
    def list_review_logs(
        self,
        point_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[ReviewLog]:
        """按时间倒序取复习日志（可按知识点过滤）。"""
        sql = "SELECT * FROM review_logs"
        params: list = []
        if point_id is not None:
            sql += " WHERE point_id = ?"
            params.append(point_id)
        sql += " ORDER BY reviewed_at DESC, id DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        return [ReviewLog.from_row(r) for r in self.conn.execute(sql, params)]

    def review_log_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS n FROM review_logs").fetchone()
        return int(row["n"])

    # --------------------------------------------------------------- 导出 --
    def export_all(self) -> dict:
        """导出全库内容（知识点 + 学习记录 + 复习日志），用于备份与迁移。"""
        def dump(table: str) -> list[dict]:
            rows = self.conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
            return [dict(r) for r in rows]

        return {
            "knowledge_points": dump("knowledge_points"),
            "learning_records": dump("learning_records"),
            "review_logs": dump("review_logs"),
        }

    # ------------------------------------------------------------- 统计 --
    def stats(self) -> dict:
        rows = self.conn.execute(
            "SELECT status, mastery, COUNT(*) AS n, COALESCE(SUM(review_count), 0) AS reviews"
            " FROM learning_records GROUP BY status, mastery"
        ).fetchall()
        total = self.conn.execute("SELECT COUNT(*) AS n FROM knowledge_points").fetchone()["n"]
        unlearned = len(self.unlearned_points())
        learning = mastered = total_reviews = 0
        distribution = {m: 0 for m in range(1, config.MASTERY_MAX + 1)}
        for r in rows:
            total_reviews += r["reviews"]
            if r["status"] == config.STATUS_MASTERED:
                mastered += r["n"]
            else:
                learning += r["n"]
            distribution[r["mastery"]] = distribution.get(r["mastery"], 0) + r["n"]
        learned = learning + mastered
        due = sum(
            1 for _, rec in self.learned_with_records()
            if rec.next_review_at <= date.today().isoformat()
        )
        return {
            "total": total,
            "unlearned": unlearned,
            "learning": learning,
            "mastered": mastered,
            "learned": learned,
            "due": due,
            "total_reviews": total_reviews,
            "mastery_distribution": distribution,
        }

    # ------------------------------------------------------------- 组装 --
    def merged(self, point: KnowledgePoint, record: Optional[LearningRecord]) -> dict:
        """知识点 + 学习记录 → 前端使用的合并视图。"""
        data = point.to_dict()
        if record is None:
            data.update(
                status=config.STATUS_UNLEARNED,
                status_label=config.STATUS_LABELS[config.STATUS_UNLEARNED],
                mastery=0, mastery_label=config.MASTERY_LABELS[0],
                review_count=0, last_reviewed_at=None,
                next_review_at=None, is_due=False,
            )
        else:
            data.update(
                status=record.status,
                status_label=config.STATUS_LABELS[record.status],
                mastery=record.mastery,
                mastery_label=config.MASTERY_LABELS[record.mastery],
                review_count=record.review_count,
                last_reviewed_at=record.last_reviewed_at,
                next_review_at=record.next_review_at,
                is_due=record.next_review_at <= date.today().isoformat(),
            )
        return data
