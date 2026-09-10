"""SQLite 连接、备份与 schema 初始化（标准库 sqlite3，零依赖）。"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from . import config, migrations


def connect(db_path: Path | str = config.DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def backup_database(
    db_path: Path | str = config.DB_PATH,
    backup_dir: Path | str = config.BACKUP_DIR,
) -> Path | None:
    """用 ``VACUUM INTO`` 生成一致性快照（可对运行中的库安全执行）。

    Returns:
        备份文件路径；库不存在或为空时返回 None。
    """
    db_path = Path(db_path)
    if not db_path.exists() or db_path.stat().st_size == 0:
        return None

    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"{db_path.stem}-{stamp}.db"
    if target.exists():  # 同一秒内重复调用
        target = backup_dir / f"{db_path.stem}-{stamp}-{os.getpid()}.db"

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("VACUUM INTO ?", (str(target),))
    finally:
        conn.close()
    return target


def init(
    db_path: Path | str = config.DB_PATH,
    backup_dir: Path | str = config.BACKUP_DIR,
) -> sqlite3.Connection:
    """确保数据目录与表结构存在（幂等），并按需应用架构迁移。

    新建库不备份（无数据可丢）；已存在的库在应用迁移前自动备份一次。
    """
    db_path = Path(db_path)
    is_fresh = not db_path.exists()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    migrations.ensure_schema(
        conn,
        backup_before=None if is_fresh else lambda: backup_database(db_path, backup_dir),
    )
    return conn
