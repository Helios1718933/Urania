"""数据仓库：知识点与学习记录的读写（Repository 层）。

上层（API / 界面）只与本模块对话，不直接碰 SQL。
所有方法即用即提交，SQLite 单文件天然适合本应用的并发规模。
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime

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
    """业务错误基类。子类通过 ``status`` 声明对应的 HTTP 状态码。"""

    status = 400


class ValidationError(RepositoryError):
    """输入不合法（名称为空、字段格式错误等）→ 400。"""

    status = 400


class NotFoundError(RepositoryError):
    """目标资源不存在 → 404。"""

    status = 404


class ConflictError(RepositoryError):
    """与现有状态冲突（重复添加、重复标记）→ 409。"""

    status = 409


class KnowledgeRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ------------------------------------------------------------- 知识点 --
    def list_points(self, category: str | None = None) -> list[KnowledgePoint]:
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
            raise NotFoundError(f"知识点不存在: {point_id}")
        return KnowledgePoint.from_row(row)

    def add_point(
        self,
        name: str,
        category: str,
        principle: str = "",
        visualization: str = "",
        tags: list[str] | None = None,
    ) -> KnowledgePoint:
        """新增知识点。重名会抛 RepositoryError。"""
        if not name.strip():
            raise ValidationError("知识点名称不能为空")
        now = date.today().isoformat()
        try:
            cur = self.conn.execute(
                "INSERT INTO knowledge_points (name, category, principle, visualization, tags,"
                " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name.strip(), category.strip(), principle.strip(), visualization.strip(),
                 ",".join(t.strip() for t in (tags or []) if t.strip()), now, now),
            )
        except sqlite3.IntegrityError:
            raise ConflictError(f"知识点已存在: {name.strip()}") from None
        self.conn.commit()
        if cur.lastrowid is None:  # 刚插入，理论上不可达
            raise RepositoryError("新增知识点后未取得主键")
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

    # --------------------------------------------------- 批量导入与改名 --
    # 可导入/更新的知识点字段（顺序与 _normalize_point 的键一致）
    POINT_FIELDS: tuple[str, ...] = (
        "name", "category", "principle", "visualization", "tags",
        "definition", "mechanism", "key_point", "code_example",
        "source", "self_test", "module", "stage", "difficulty",
    )

    @staticmethod
    def _normalize_point(raw: dict) -> dict:
        """把外部数据（如 Mnemosyne 的条目）规整成入库用的字典。"""
        def text(key: str) -> str:
            return str(raw.get(key) or "").strip()

        tags = raw.get("tags") or []
        return {
            "name": text("name"),
            "category": text("category") or "未分类",
            "principle": text("principle"),
            "visualization": text("visualization"),
            "tags": ",".join(str(t).strip() for t in tags if str(t).strip()),
            "definition": text("definition"),
            "mechanism": text("mechanism"),
            "key_point": text("key_point"),
            "code_example": text("code_example"),
            "source": text("source"),
            "self_test": text("self_test"),
            "module": text("module"),
            "stage": int(raw.get("stage") or 1),
            "difficulty": int(raw.get("difficulty") or 0),
        }

    @staticmethod
    def _point_unchanged(current: KnowledgePoint, data: dict) -> bool:
        """内容是否与库中一致（用于统计「未变化」，避免无谓写库）。"""
        for field in KnowledgeRepository.POINT_FIELDS:
            wanted = data[field].split(",") if field == "tags" else data[field]
            if getattr(current, field) != wanted:
                return False
        return True

    def upsert_points(self, items: list[dict]) -> dict:
        """按名称导入或更新知识点。

        与 ``upsert_seed`` 的区别：**已存在的条目会被更新**为新内容。
        学习记录与复习日志挂在 point_id 上，因此不受改名或内容更新影响。

        Returns:
            ``{"inserted": n, "updated": n, "unchanged": n}``
        """
        now = date.today().isoformat()
        stats = {"inserted": 0, "updated": 0, "unchanged": 0}
        columns = ", ".join(self.POINT_FIELDS)
        placeholders = ", ".join("?" for _ in self.POINT_FIELDS)
        assignments = ", ".join(f"{field} = ?" for field in self.POINT_FIELDS)

        for raw in items:
            data = self._normalize_point(raw)
            if not data["name"]:
                continue

            row = self.conn.execute(
                "SELECT * FROM knowledge_points WHERE name = ?", (data["name"],)
            ).fetchone()

            if row is None:
                self.conn.execute(
                    f"INSERT INTO knowledge_points ({columns}, created_at, updated_at)"
                    f" VALUES ({placeholders}, ?, ?)",
                    (*[data[f] for f in self.POINT_FIELDS], now, now),
                )
                stats["inserted"] += 1
                continue

            if self._point_unchanged(KnowledgePoint.from_row(row), data):
                stats["unchanged"] += 1
                continue

            self.conn.execute(
                f"UPDATE knowledge_points SET {assignments}, updated_at = ? WHERE id = ?",
                (*[data[f] for f in self.POINT_FIELDS], now, row["id"]),
            )
            stats["updated"] += 1

        self.conn.commit()
        return stats

    def rename_point(self, old_name: str, new_name: str) -> bool:
        """按名称改知识点名（导入时对齐旧条目用）。

        学习记录挂在 point_id 上，改名不会丢学习进度。
        目标名已存在时不动（避免 UNIQUE 冲突）并返回 False。
        """
        row = self.conn.execute(
            "SELECT id FROM knowledge_points WHERE name = ?", (old_name,)
        ).fetchone()
        if row is None:
            return False
        taken = self.conn.execute(
            "SELECT 1 FROM knowledge_points WHERE name = ?", (new_name,)
        ).fetchone()
        if taken is not None:
            return False
        self.conn.execute(
            "UPDATE knowledge_points SET name = ?, updated_at = ? WHERE id = ?",
            (new_name, date.today().isoformat(), row["id"]),
        )
        self.conn.commit()
        return True

    # ------------------------------------------------------------- 学习记录 --
    def get_record(self, point_id: int) -> LearningRecord | None:
        row = self.conn.execute(
            "SELECT * FROM learning_records WHERE point_id = ?", (point_id,)
        ).fetchone()
        return LearningRecord.from_row(row) if row else None

    def point_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS n FROM knowledge_points").fetchone()
        return int(row["n"])

    def unlearned_points(self) -> list[KnowledgePoint]:
        """所有「未标注」知识点：没有学习记录的那些。"""
        rows = self.conn.execute(
            "SELECT p.* FROM knowledge_points p"
            " LEFT JOIN learning_records r ON r.point_id = p.id"
            " WHERE r.id IS NULL ORDER BY p.id"
        ).fetchall()
        return [KnowledgePoint.from_row(r) for r in rows]

    def learned_with_records(self) -> list[tuple[KnowledgePoint, LearningRecord]]:
        """已学习知识点及其当前记录。

        单次 JOIN 取回两表（原实现每条再单独查一次记录，即 N+1）；
        r 的列全部起别名，避免与 ``p.*`` 的 id/created_at 等重名。
        """
        rows = self.conn.execute(
            "SELECT p.*,"
            " r.id AS r_id, r.status, r.mastery, r.review_count, r.last_reviewed_at,"
            " r.next_review_at, r.created_at AS r_created_at, r.updated_at AS r_updated_at"
            " FROM knowledge_points p JOIN learning_records r ON r.point_id = p.id"
            " ORDER BY r.next_review_at, r.mastery, r.last_reviewed_at"
        ).fetchall()
        return [(KnowledgePoint.from_row(r), self._record_from_join(r)) for r in rows]

    @staticmethod
    def _record_from_join(row: sqlite3.Row) -> LearningRecord:
        """从 JOIN 结果行还原学习记录（列名带 r_ 前缀）。"""
        return LearningRecord(
            id=row["r_id"],
            point_id=row["id"],
            status=row["status"],
            mastery=row["mastery"],
            review_count=row["review_count"],
            last_reviewed_at=row["last_reviewed_at"],
            next_review_at=row["next_review_at"],
            created_at=row["r_created_at"],
            updated_at=row["r_updated_at"],
        )

    def mark_learned(self, point_id: int, initial_mastery: int) -> LearningRecord:
        """把知识点标记为已学习：同一事务写入学习记录 + 追加首条日志。

        initial_mastery 取 1~3（越界自动收敛）。
        """
        self.get_point(point_id)  # 不存在则抛错
        initial_mastery = max(config.MASTERY_MIN, min(3, int(initial_mastery)))
        if self.get_record(point_id) is not None:
            raise ConflictError(f"该知识点已在学习循环中: {point_id}")

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
            raise NotFoundError(f"学习记录不存在: {point_id}")

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

    def reset_point(self, point_id: int) -> bool:
        """删除学习记录，让知识点回到「未标注 / 未学习」状态。

        review_logs 中的历史不受影响（外键指向知识点而非学习记录），
        因此重置不会抹掉已经积累的复习历史。

        Returns:
            True 表示确实删除了记录；False 表示本来就没有记录（幂等成功）。

        Raises:
            NotFoundError: 知识点本身不存在。
        """
        self.get_point(point_id)  # 不存在则抛 NotFoundError
        cur = self.conn.execute(
            "DELETE FROM learning_records WHERE point_id = ?", (point_id,)
        )
        self.conn.commit()
        return cur.rowcount > 0

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
        rating: str | None,
        reviewed_at: str,
        elapsed_days: int | None,
        scheduled_days: int | None,
        prev_mastery: int | None,
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
        point_id: int | None = None,
        limit: int | None = None,
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
        distribution = dict.fromkeys(range(1, config.MASTERY_MAX + 1), 0)
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
    def merged(self, point: KnowledgePoint, record: LearningRecord | None) -> dict:
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
