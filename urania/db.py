"""SQLite 连接与 schema 管理（标准库 sqlite3，零依赖）。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_points (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    category      TEXT NOT NULL,
    principle     TEXT NOT NULL DEFAULT '',
    visualization TEXT NOT NULL DEFAULT '',
    tags          TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

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
);

CREATE INDEX IF NOT EXISTS idx_records_status ON learning_records(status);
CREATE INDEX IF NOT EXISTS idx_points_category ON knowledge_points(category);
"""


def connect(db_path: Path | str = config.DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init(db_path: Path | str = config.DB_PATH) -> sqlite3.Connection:
    """确保数据目录与表结构存在（幂等）。"""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
