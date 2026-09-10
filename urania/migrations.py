"""Schema 版本管理与迁移（零依赖，标准库实现）。

机制
----
- 版本号以 SQLite 官方的 ``PRAGMA user_version`` 为唯一事实来源（整数，事务内原子）
- ``schema_migrations`` 表仅作审计日志（何时应用了哪个迁移），不参与判定
- ``MIGRATIONS`` 是有序列表，启动时对比当前版本，依次应用未执行的迁移
- 应用迁移前先 ``VACUUM INTO`` 备份（库非空时）；备份失败即中止迁移
- 迁移函数必须用 ``conn.execute()`` 逐条执行，**不能用 executescript()**
  （后者会隐式提交，破坏迁移的事务性）

新增迁移的步骤
--------------
1. 写一个 ``def _migration_NNN_xxx(conn)`` 函数，内部只做 DDL/DML
2. 追加到 ``MIGRATIONS`` 末尾，版本号必须连续递增
3. 补一条测试到 ``tests/test_migrations.py``
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

Migration = tuple[int, str, Callable[[sqlite3.Connection], None]]

# 基线 schema：首次建库（version 0）时的表结构。
# 已存在的库执行时是幂等的（IF NOT EXISTS），不会覆盖数据。
BASELINE_SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS knowledge_points (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        name          TEXT NOT NULL UNIQUE,
        category      TEXT NOT NULL,
        principle     TEXT NOT NULL DEFAULT '',
        visualization TEXT NOT NULL DEFAULT '',
        tags          TEXT NOT NULL DEFAULT '',
        created_at    TEXT NOT NULL,
        updated_at    TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS learning_records (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        point_id         INTEGER NOT NULL UNIQUE REFERENCES knowledge_points(id) ON DELETE CASCADE,
        status           TEXT NOT NULL DEFAULT 'learning',
        mastery          INTEGER NOT NULL DEFAULT 1,
        review_count     INTEGER NOT NULL DEFAULT 0,
        last_reviewed_at TEXT NOT NULL,
        next_review_at   TEXT NOT NULL,
        created_at       TEXT NOT NULL,
        updated_at       TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_records_status ON learning_records(status)",
    "CREATE INDEX IF NOT EXISTS idx_points_category ON knowledge_points(category)",
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version     INTEGER PRIMARY KEY,
        description TEXT NOT NULL,
        applied_at  TEXT NOT NULL
    )
    """,
)


# --------------------------------------------------------------------- 迁移 --

def _migration_001_review_logs(conn: sqlite3.Connection) -> None:
    """v1：新增 review_logs 只追加表（对标 Anki 的 revlog）。

    设计要点：学习记录表 learning_records 存「当前状态」（每点一行，会被覆盖），
    本表存「历史事件」（每次标记/复习追加一行，永不修改），
    两者分离后才能真正统计遗忘曲线、真实保留率，并为将来的调度算法优化留数据。
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS review_logs (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            point_id       INTEGER NOT NULL REFERENCES knowledge_points(id) ON DELETE CASCADE,
            source         TEXT NOT NULL,
            rating         TEXT,
            reviewed_at    TEXT NOT NULL,
            elapsed_days   INTEGER,
            scheduled_days INTEGER,
            prev_mastery   INTEGER,
            new_mastery    INTEGER NOT NULL,
            created_at     TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_review_logs_point"
        " ON review_logs(point_id, reviewed_at)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_review_logs_time ON review_logs(reviewed_at)")


# v2 新增的列：知识点从「一段原理」升级为四段式结构 + 学习元信息
# （来自 Mnemosyne 知识库；老数据这些列保持默认空值，前端会回退到 principle）
RICH_COLUMNS: tuple[tuple[str, str], ...] = (
    ("definition", "TEXT NOT NULL DEFAULT ''"),    # ① 一句话定义
    ("mechanism", "TEXT NOT NULL DEFAULT ''"),     # ② 原理机制
    ("key_point", "TEXT NOT NULL DEFAULT ''"),     # ③ 面试/实战要点
    ("code_example", "TEXT NOT NULL DEFAULT ''"),  # ④ 代码例子（markdown 围栏）
    ("source", "TEXT NOT NULL DEFAULT ''"),        # 出处锚点
    ("self_test", "TEXT NOT NULL DEFAULT ''"),     # 自测关卡
    ("module", "TEXT NOT NULL DEFAULT ''"),        # 模块码（如 M04）
    ("stage", "INTEGER NOT NULL DEFAULT 1"),       # 阶段 1 / 2
    ("difficulty", "INTEGER NOT NULL DEFAULT 0"),  # 1~5，0 表示未标定
)


def _migration_002_rich_fields(conn: sqlite3.Connection) -> None:
    """v2：知识点支持四段式结构与学习元信息。"""
    for name, declaration in RICH_COLUMNS:
        conn.execute(f"ALTER TABLE knowledge_points ADD COLUMN {name} {declaration}")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_points_module ON knowledge_points(module)"
    )


MIGRATIONS: tuple[Migration, ...] = (
    (1, "add review_logs append-only table", _migration_001_review_logs),
    (2, "add rich knowledge fields (structured four-part + study metadata)",
     _migration_002_rich_fields),
)

LATEST_VERSION = MIGRATIONS[-1][0] if MIGRATIONS else 0


# ----------------------------------------------------------------- 查询/执行 --

def current_version(conn: sqlite3.Connection) -> int:
    """读取当前 schema 版本（PRAGMA user_version）。"""
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def pending_migrations(conn: sqlite3.Connection) -> list[Migration]:
    """返回尚未应用的迁移（按版本号升序）。"""
    version = current_version(conn)
    return [m for m in MIGRATIONS if m[0] > version]


def ensure_schema(conn: sqlite3.Connection, backup_before: Callable[[], Path | None] | None = None) -> list[int]:
    """建基线表并依次应用未执行的迁移。

    Args:
        conn: 已打开的数据库连接。
        backup_before: 无参回调，返回备份文件路径（或 None 表示无需备份）。
            仅在有待应用迁移时调用；返回 None 或抛异常都会影响流程：
            - 返回 None：视为「无需备份」，继续迁移
            - 抛异常：中止迁移并把异常抛给调用方

    Returns:
        本次实际应用的迁移版本号列表（无迁移时为空列表）。
    """
    for statement in BASELINE_SCHEMA:
        conn.execute(statement)
    conn.commit()

    pending = pending_migrations(conn)
    if not pending:
        return []

    logger.info("发现 %d 个待应用的架构迁移（当前版本 %d）", len(pending), current_version(conn))
    if backup_before is not None:
        backup_path = backup_before()
        if backup_path is not None:
            logger.info("迁移前已备份数据库: %s", backup_path)

    applied: list[int] = []
    for version, description, migrate in pending:
        logger.info("应用迁移 v%d: %s", version, description)
        try:
            conn.execute("BEGIN")
            migrate(conn)
            conn.execute(
                "INSERT INTO schema_migrations (version, description, applied_at)"
                " VALUES (?, ?, datetime('now', 'localtime'))",
                (version, description),
            )
            # PRAGMA 不支持参数绑定，版本号来自代码内常量（非用户输入）
            conn.execute(f"PRAGMA user_version = {int(version)}")
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("迁移 v%d 失败，已回滚", version)
            raise
        applied.append(version)

    logger.info("架构迁移完成，当前版本 %d", current_version(conn))
    return applied
