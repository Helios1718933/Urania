"""数据目录搬迁测试（旧版项目内 data/ → 用户数据目录）。"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from urania import db


class TestMigrateLegacyData(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.legacy = root / "project" / "data"
        self.target = root / "appsupport" / "Urania"
        self.legacy.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def make_legacy_db(self, name: str = "urania.db", content: bytes = b"SQLite format 3\x00demo"):
        path = self.legacy / name
        path.write_bytes(content)
        return path

    def test_no_legacy_dir_returns_empty(self):
        empty = Path(self._tmp.name) / "not-there"
        self.assertEqual(db.migrate_legacy_data(empty, self.target), [])
        self.assertFalse(self.target.exists())

    def test_same_dir_is_noop(self):
        self.assertEqual(db.migrate_legacy_data(self.legacy, self.legacy), [])

    def test_migrates_database_and_token(self):
        self.make_legacy_db()
        (self.legacy / ".token").write_text("abc12345\n", encoding="utf-8")

        moved = db.migrate_legacy_data(self.legacy, self.target)

        self.assertIn("urania.db", moved)
        self.assertIn(".token", moved)
        self.assertTrue((self.target / "urania.db").exists())
        self.assertEqual((self.target / ".token").read_text(encoding="utf-8").strip(), "abc12345")

    def test_migrates_backup_files(self):
        self.make_legacy_db()
        backups = self.legacy / "backups"
        backups.mkdir()
        (backups / "urania-20260101-000000.db").write_bytes(b"snapshot")

        moved = db.migrate_legacy_data(self.legacy, self.target)

        self.assertIn("backups/urania-20260101-000000.db", moved)
        self.assertTrue((self.target / "backups" / "urania-20260101-000000.db").exists())

    def test_does_not_overwrite_existing_target(self):
        self.make_legacy_db(content=b"OLD")
        self.target.mkdir(parents=True)
        (self.target / "urania.db").write_bytes(b"NEW")

        moved = db.migrate_legacy_data(self.legacy, self.target)

        self.assertNotIn("urania.db", moved)
        self.assertEqual((self.target / "urania.db").read_bytes(), b"NEW", "已有数据优先")

    def test_is_idempotent(self):
        self.make_legacy_db()
        first = db.migrate_legacy_data(self.legacy, self.target)
        second = db.migrate_legacy_data(self.legacy, self.target)
        self.assertIn("urania.db", first)
        self.assertEqual(second, [], "第二次应无事可做")

    def test_seed_file_is_not_migrated(self):
        """种子数据是只读资源，应留在项目内。"""
        (self.legacy / "seed_knowledge.json").write_text("[]", encoding="utf-8")
        moved = db.migrate_legacy_data(self.legacy, self.target)
        self.assertNotIn("seed_knowledge.json", moved)
        self.assertFalse((self.target / "seed_knowledge.json").exists())

    def test_migrated_database_still_opens(self):
        """搬过去的库应能被 sqlite 正常打开（内容完整）。"""
        source = sqlite3.connect(str(self.legacy / "real.db"))
        source.execute("CREATE TABLE t (x INTEGER)")
        source.execute("INSERT INTO t VALUES (42)")
        source.commit()
        source.close()
        (self.legacy / "real.db").rename(self.legacy / "urania.db")

        db.migrate_legacy_data(self.legacy, self.target)

        conn = sqlite3.connect(str(self.target / "urania.db"))
        try:
            self.assertEqual(conn.execute("SELECT x FROM t").fetchone()[0], 42)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
