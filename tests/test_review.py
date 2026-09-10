"""复习与掌握度更新逻辑（SRS-lite）。"""
from __future__ import annotations

import unittest
from datetime import date, timedelta

from urania import config
from urania.models import LearningRecord
from urania.review import apply_rating, next_interval_days


def _record(mastery=2):
    return LearningRecord(id=1, point_id=1, mastery=mastery, review_count=0,
                          last_reviewed_at="2026-01-01T00:00:00",
                          next_review_at=date.today().isoformat())


class TestApplyRating(unittest.TestCase):
    def test_invalid_rating_raises(self):
        with self.assertRaises(ValueError):
            apply_rating(_record(), "excellent")

    def test_solid_increases_mastery(self):
        r = apply_rating(_record(mastery=2), "solid")
        self.assertEqual(r.mastery, 3)
        self.assertEqual(r.review_count, 1)

    def test_forgot_decreases_but_floor_1(self):
        r = apply_rating(_record(mastery=1), "forgot")
        self.assertEqual(r.mastery, 1)

    def test_fuzzy_keeps_mastery(self):
        r = apply_rating(_record(mastery=3), "fuzzy")
        self.assertEqual(r.mastery, 3)

    def test_mastery_capped_at_5(self):
        r = apply_rating(_record(mastery=5), "solid")
        self.assertEqual(r.mastery, config.MASTERY_MAX)

    def test_mastered_status_at_threshold(self):
        r = apply_rating(_record(mastery=3), "solid")   # 3 → 4
        self.assertEqual(r.status, config.STATUS_MASTERED)
        r2 = apply_rating(_record(mastery=4), "forgot")  # 4 → 3
        self.assertEqual(r2.status, config.STATUS_LEARNING)

    def test_next_review_dates(self):
        r = apply_rating(_record(mastery=2), "solid")    # 新掌握度 3 → 5 天后
        self.assertEqual(r.next_review_at, (date.today() + timedelta(days=5)).isoformat())
        r2 = apply_rating(_record(mastery=3), "forgot")  # 明天
        self.assertEqual(r2.next_review_at, (date.today() + timedelta(days=1)).isoformat())

    def test_interval_table(self):
        self.assertEqual(next_interval_days(1, "solid"), 1)
        self.assertEqual(next_interval_days(3, "fuzzy"), 5)
        self.assertEqual(next_interval_days(4, "forgot"), 1)  # forgot 永远明天
        self.assertEqual(next_interval_days(5, "solid"), 15)

    def test_last_reviewed_updated(self):
        r = apply_rating(_record(mastery=2), "fuzzy")
        self.assertTrue(r.last_reviewed_at.startswith(str(date.today())))


if __name__ == "__main__":
    unittest.main()
