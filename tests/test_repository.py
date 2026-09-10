"""数据仓库（Repository）行为测试。"""
from __future__ import annotations

import unittest

from common import RepoTestCase

from urania.repository import RepositoryError


class TestKnowledgePoints(RepoTestCase):
    def test_seed_inserted(self):
        self.assertEqual(len(self.repo.list_points()), 10)

    def test_seed_skipped_when_db_not_empty(self):
        """库非空时不补种：否则重命名/导入过的条目会被旧名字重新插回来。"""
        from urania import seed
        added = seed.seed_if_needed(self.repo, [
            {"name": "全新知识点", "category": "x", "principle": "", "tags": []},
        ])
        self.assertEqual(added, 0, "库非空时不应补种")
        self.assertEqual(len(self.repo.list_points()), 10, "条目数不应变化")

    def test_seed_runs_on_empty_db(self):
        import tempfile
        from pathlib import Path as _Path

        from urania import db, seed
        from urania.repository import KnowledgeRepository

        with tempfile.TemporaryDirectory() as tmp:
            conn = db.init(_Path(tmp) / "empty.db")
            try:
                fresh = KnowledgeRepository(conn)
                added = seed.seed_if_needed(fresh, [
                    {"name": "起步知识点", "category": "x", "principle": "", "tags": []},
                ])
                self.assertEqual(added, 1, "空库应导入种子")
                self.assertEqual(len(fresh.list_points()), 1)
            finally:
                conn.close()

    def test_add_duplicate_raises(self):
        with self.assertRaises(RepositoryError):
            self.repo.add_point("测试知识点1", "Python 基础")

    def test_get_missing_raises(self):
        with self.assertRaises(RepositoryError):
            self.repo.get_point(99999)


class TestLearningRecords(RepoTestCase):
    def test_mark_learned_creates_record(self):
        pid = self.all_ids()[0]
        rec = self.repo.mark_learned(pid, 2)
        self.assertEqual(rec.mastery, 2)
        self.assertEqual(rec.review_count, 0)

    def test_mark_learned_twice_raises(self):
        pid = self.all_ids()[0]
        self.repo.mark_learned(pid, 1)
        with self.assertRaises(RepositoryError):
            self.repo.mark_learned(pid, 1)

    def test_mark_learned_clamps_mastery_to_1_3(self):
        pid = self.all_ids()[0]
        self.assertEqual(self.repo.mark_learned(pid, 9).mastery, 3)
        pid2 = self.all_ids()[1]
        self.assertEqual(self.repo.mark_learned(pid2, 0).mastery, 1)

    def test_unlearned_excludes_learned(self):
        ids = self.all_ids()
        self.repo.mark_learned(ids[0], 1)
        self.repo.mark_learned(ids[1], 2)
        unlearned = self.repo.unlearned_points()
        self.assertEqual(len(unlearned), 8)
        self.assertNotIn(ids[0], [p.id for p in unlearned])

    def test_reset_point_back_to_unlearned(self):
        pid = self.all_ids()[0]
        self.repo.mark_learned(pid, 3)
        self.repo.reset_point(pid)
        self.assertIsNone(self.repo.get_record(pid))
        self.assertIn(pid, [p.id for p in self.repo.unlearned_points()])
        # 重置后可再次标记学习
        self.repo.mark_learned(pid, 1)

    def test_stats(self):
        ids = self.all_ids()
        # 初始掌握度上限 3（熟悉）；复习一次 solid 达到 4 级才算「已掌握」
        self.repo.mark_learned(ids[0], 3)
        self.repo.apply_review(ids[0], "solid")
        self.repo.mark_learned(ids[1], 2)   # 学习中
        s = self.repo.stats()
        self.assertEqual(s["total"], 10)
        self.assertEqual(s["unlearned"], 8)
        self.assertEqual(s["learned"], 2)
        self.assertEqual(s["mastered"], 1)
        self.assertEqual(s["learning"], 1)
        self.assertEqual(s["mastery_distribution"][4], 1)
        self.assertEqual(s["mastery_distribution"][2], 1)
        self.assertEqual(s["total_reviews"], 1)

    def test_merged_view_fields(self):
        pid = self.all_ids()[0]
        self.repo.mark_learned(pid, 3)
        data = self.repo.merged(self.repo.get_point(pid), self.repo.get_record(pid))
        self.assertEqual(data["status"], "learning")
        self.assertEqual(data["mastery"], 3)
        self.assertIn("status_label", data)
        self.assertIn("is_due", data)

    def test_merged_unlearned_defaults(self):
        pid = self.all_ids()[0]
        data = self.repo.merged(self.repo.get_point(pid), None)
        self.assertEqual(data["status"], "unlearned")
        self.assertEqual(data["mastery"], 0)


if __name__ == "__main__":
    unittest.main()
