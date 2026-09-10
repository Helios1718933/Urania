"""架构迁移机制测试（migrations.py + db.init）。"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from common import PROJECT_ROOT  # noqa: F401  确保包可导入

from urania import db, migrations


class MigrationTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.db_path = self.root / "test.db"
        self.backup_dir = self.root / "backups"

    def tearDown(self):
        self._tmp.cleanup()

    # ------------------------------------------------------------ 工具 --
    def make_legacy_db(self) -> None:
        """造一个「旧版」库：只有基线表、user_version=0、无 review_logs。"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        for statement in migrations.BASELINE_SCHEMA:
            if "schema_migrations" in statement:
                continue  # 旧库没有这张审计表
            if "review_logs" in statement:
                continue
            conn.execute(statement)
        conn.execute(
            "INSERT INTO knowledge_points (name, category, principle, visualization,"
            " tags, created_at, updated_at) VALUES ('旧知识点', '测试', '', '', '',"
            " '2026-01-01', '2026-01-01')"
        )
        conn.commit()
        conn.close()

    def table_names(self, conn: sqlite3.Connection) -> set[str]:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {r["name"] for r in rows}


class TestFreshDatabase(MigrationTestCase):
    def test_fresh_db_reaches_latest_version(self):
        conn = db.init(self.db_path, backup_dir=self.backup_dir)
        try:
            self.assertEqual(migrations.current_version(conn), migrations.LATEST_VERSION)
            tables = self.table_names(conn)
            self.assertIn("knowledge_points", tables)
            self.assertIn("learning_records", tables)
            self.assertIn("review_logs", tables)
            self.assertIn("schema_migrations", tables)
        finally:
            conn.close()

    def test_fresh_db_creates_no_backup(self):
        db.init(self.db_path, backup_dir=self.backup_dir).close()
        self.assertFalse(self.backup_dir.exists(), "新建库不应产生备份")

    def test_init_is_idempotent(self):
        db.init(self.db_path, backup_dir=self.backup_dir).close()
        conn = db.init(self.db_path, backup_dir=self.backup_dir)
        try:
            self.assertEqual(migrations.current_version(conn), migrations.LATEST_VERSION)
            applied = conn.execute("SELECT COUNT(*) AS n FROM schema_migrations").fetchone()["n"]
            self.assertEqual(applied, len(migrations.MIGRATIONS))
        finally:
            conn.close()

    def test_second_init_creates_no_extra_backup(self):
        db.init(self.db_path, backup_dir=self.backup_dir).close()
        db.init(self.db_path, backup_dir=self.backup_dir).close()
        self.assertFalse(self.backup_dir.exists(), "无待应用迁移时不应重复备份")


class TestLegacyUpgrade(MigrationTestCase):
    def test_legacy_db_upgraded_and_backed_up(self):
        self.make_legacy_db()
        conn = db.init(self.db_path, backup_dir=self.backup_dir)
        try:
            # 版本推进
            self.assertEqual(migrations.current_version(conn), migrations.LATEST_VERSION)
            # 新表出现
            self.assertIn("review_logs", self.table_names(conn))
            # 旧数据保留
            row = conn.execute("SELECT name FROM knowledge_points").fetchone()
            self.assertEqual(row["name"], "旧知识点")
            # 审计记录写入
            versions = [r["version"] for r in
                        conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
            self.assertEqual(versions, [m[0] for m in migrations.MIGRATIONS])
        finally:
            conn.close()

        # 备份文件已生成且可独立打开
        backups = list(self.backup_dir.glob("*.db"))
        self.assertEqual(len(backups), 1, "升级旧库前应生成一次备份")
        snapshot = sqlite3.connect(str(backups[0]))
        try:
            self.assertEqual(snapshot.execute("SELECT COUNT(*) FROM knowledge_points").fetchone()[0], 1)
        finally:
            snapshot.close()

    def test_backup_snapshot_is_before_migration(self):
        """备份应是迁移前的状态：不含 review_logs 表。"""
        self.make_legacy_db()
        db.init(self.db_path, backup_dir=self.backup_dir).close()
        backup = next(self.backup_dir.glob("*.db"))
        snapshot = sqlite3.connect(str(backup))
        try:
            tables = {r[0] for r in snapshot.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertNotIn("review_logs", tables, "备份必须早于迁移执行")
        finally:
            snapshot.close()


class TestBackupHelper(MigrationTestCase):
    def test_backup_missing_db_returns_none(self):
        self.assertIsNone(db.backup_database(self.db_path, self.backup_dir))

    def test_backup_empty_file_returns_none(self):
        self.db_path.write_bytes(b"")
        self.assertIsNone(db.backup_database(self.db_path, self.backup_dir))

    def test_backup_creates_readable_snapshot(self):
        db.init(self.db_path, backup_dir=self.backup_dir).close()
        path = db.backup_database(self.db_path, self.backup_dir)
        self.assertIsNotNone(path)
        assert path is not None
        self.assertTrue(path.exists())
        snapshot = sqlite3.connect(str(path))
        try:
            self.assertEqual(snapshot.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        finally:
            snapshot.close()

    def test_same_second_backups_do_not_collide(self):
        db.init(self.db_path, backup_dir=self.backup_dir).close()
        first = db.backup_database(self.db_path, self.backup_dir)
        second = db.backup_database(self.db_path, self.backup_dir)
        self.assertNotEqual(first, second, "同一秒内的两次备份不应覆盖")


if __name__ == "__main__":
    unittest.main()
