"""复习日志（review_logs）行为测试。"""
from __future__ import annotations

import unittest

from common import RepoTestCase

from urania.models import SOURCE_LEARN, SOURCE_REVIEW
from urania.repository import RepositoryError


class TestLearnLogging(RepoTestCase):
    def test_mark_learned_appends_learn_log(self):
        pid = self.all_ids()[0]
        self.repo.mark_learned(pid, 2)

        logs = self.repo.list_review_logs(pid)
        self.assertEqual(len(logs), 1)
        log = logs[0]
        self.assertEqual(log.source, SOURCE_LEARN)
        self.assertIsNone(log.rating, "标记学习没有自评档位")
        self.assertIsNone(log.prev_mastery, "首次事件的变更前掌握度为空")
        self.assertIsNone(log.elapsed_days, "首次事件没有「距上次复习」")
        self.assertEqual(log.new_mastery, 2)
        self.assertEqual(log.scheduled_days, 0, "标记学习当天即到期")

    def test_mastery_is_clamped_in_log(self):
        pid = self.all_ids()[0]
        self.repo.mark_learned(pid, 9)          # 越界 → 收敛到 3
        self.assertEqual(self.repo.list_review_logs(pid)[0].new_mastery, 3)


class TestReviewLogging(RepoTestCase):
    def test_apply_review_appends_log_with_correct_fields(self):
        pid = self.all_ids()[0]
        self.repo.mark_learned(pid, 2)
        self.repo.apply_review(pid, "solid")

        logs = self.repo.list_review_logs(pid)      # 时间倒序
        self.assertEqual(len(logs), 2)
        latest = logs[0]
        self.assertEqual(latest.source, SOURCE_REVIEW)
        self.assertEqual(latest.rating, "solid")
        self.assertEqual(latest.prev_mastery, 2)
        self.assertEqual(latest.new_mastery, 3)
        self.assertEqual(latest.elapsed_days, 0, "当天标记当天复习")
        self.assertEqual(latest.scheduled_days, 5, "mastery 3 对应 5 天间隔")

    def test_forgot_schedules_one_day(self):
        pid = self.all_ids()[0]
        self.repo.mark_learned(pid, 3)
        self.repo.apply_review(pid, "forgot")
        latest = self.repo.list_review_logs(pid)[0]
        self.assertEqual(latest.new_mastery, 2)
        self.assertEqual(latest.scheduled_days, 1)

    def test_fuzzy_keeps_mastery(self):
        pid = self.all_ids()[0]
        self.repo.mark_learned(pid, 3)
        self.repo.apply_review(pid, "fuzzy")
        latest = self.repo.list_review_logs(pid)[0]
        self.assertEqual(latest.prev_mastery, 3)
        self.assertEqual(latest.new_mastery, 3)

    def test_review_without_record_raises(self):
        with self.assertRaises(RepositoryError):
            self.repo.apply_review(self.all_ids()[0], "solid")

    def test_mastered_transition_is_logged(self):
        pid = self.all_ids()[0]
        self.repo.mark_learned(pid, 3)
        self.repo.apply_review(pid, "solid")        # 3 → 4，进入 mastered
        self.assertEqual(self.repo.get_record(pid).status, "mastered")
        self.assertEqual(self.repo.list_review_logs(pid)[0].new_mastery, 4)


class TestLogInvariants(RepoTestCase):
    def test_log_failure_rolls_back_record_write(self):
        """日志写入失败时，学习记录也必须回滚（同事务）。"""
        pid = self.all_ids()[0]

        def boom(*args, **kwargs):
            raise RuntimeError("模拟日志写入失败")

        self.repo._log_review = boom  # type: ignore[method-assign]
        with self.assertRaises(RuntimeError):
            self.repo.mark_learned(pid, 2)

        self.assertIsNone(self.repo.get_record(pid), "事务应整体回滚")
        self.assertEqual(self.repo.review_log_count(), 0)

    def test_logs_survive_reset(self):
        pid = self.all_ids()[0]
        self.repo.mark_learned(pid, 2)
        self.repo.apply_review(pid, "solid")
        self.repo.reset_point(pid)

        self.assertIsNone(self.repo.get_record(pid))
        self.assertEqual(len(self.repo.list_review_logs(pid)), 2, "重置不应抹掉历史")

    def test_log_count_across_points(self):
        ids = self.all_ids()
        self.repo.mark_learned(ids[0], 1)
        self.repo.apply_review(ids[0], "fuzzy")
        self.repo.mark_learned(ids[1], 1)
        self.assertEqual(self.repo.review_log_count(), 3)

    def test_list_limit_and_order(self):
        pid = self.all_ids()[0]
        self.repo.mark_learned(pid, 1)
        self.repo.apply_review(pid, "solid")
        self.repo.apply_review(pid, "solid")

        self.assertEqual(len(self.repo.list_review_logs(pid, limit=2)), 2)
        times = [log.reviewed_at for log in self.repo.list_review_logs(pid)]
        self.assertEqual(times, sorted(times, reverse=True), "日志按时间倒序")

    def test_logs_are_isolated_per_point(self):
        ids = self.all_ids()
        self.repo.mark_learned(ids[0], 1)
        self.repo.mark_learned(ids[1], 1)
        self.assertEqual(len(self.repo.list_review_logs(ids[0])), 1)
        self.assertEqual(len(self.repo.list_review_logs(ids[1])), 1)
        self.assertEqual(len(self.repo.list_review_logs()), 2)


class TestExport(RepoTestCase):
    def test_export_contains_all_tables(self):
        pid = self.all_ids()[0]
        self.repo.mark_learned(pid, 3)
        self.repo.apply_review(pid, "solid")

        data = self.repo.export_all()
        self.assertEqual(set(data), {"knowledge_points", "learning_records", "review_logs"})
        self.assertEqual(len(data["knowledge_points"]), 10)
        self.assertEqual(len(data["learning_records"]), 1)
        self.assertEqual(len(data["review_logs"]), 2)

    def test_export_rows_are_plain_dicts(self):
        data = self.repo.export_all()
        point = data["knowledge_points"][0]
        self.assertIsInstance(point, dict)
        self.assertIn("name", point)
        self.assertIn("category", point)


if __name__ == "__main__":
    unittest.main()
