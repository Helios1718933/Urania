"""导入相关测试：结构化字段读取、批量 upsert、改名对齐。

其中 `test_row_containment_semantics` 是针对一个真实踩过的坑：
`sqlite3.Row` 的 `in` 迭代的是**值**而不是列名，写成 `"tags" in row`
会让所有字段读成默认值（结构化渲染全空）。
"""
from __future__ import annotations

import sqlite3
import unittest

from common import RepoTestCase


class TestRowContainment(RepoTestCase):
    """回归测试：sqlite3.Row 的 in 语义。"""

    def test_row_containment_semantics(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT 1 AS alpha, 'beta' AS gamma").fetchone()
        self.assertFalse("alpha" in row, "sqlite3.Row 的 in 迭代值，不是列名")
        self.assertTrue("alpha" in row.keys(), "判断列必须用 row.keys()")
        conn.close()

    def test_structured_fields_roundtrip(self):
        """四段式字段必须能从数据库行还原（读不出就会静默退化为旧渲染）。"""
        pid = self.all_ids()[0]
        conn = self.repo.conn
        conn.execute(
            "UPDATE knowledge_points SET definition=?, mechanism=?, key_point=?,"
            " code_example=?, source=?, self_test=?, module=?, stage=?, difficulty=?,"
            " tags=? WHERE id=?",
            ("定义文本", "机制文本", "要点文本", "```python\nx=1\n```",
             "Python-100-Days Day17", "手写 @timer", "M04", 2, 3,
             "高频面试,八股", pid),
        )
        conn.commit()

        point = self.repo.get_point(pid)
        self.assertEqual(point.definition, "定义文本")
        self.assertEqual(point.mechanism, "机制文本")
        self.assertEqual(point.key_point, "要点文本")
        self.assertEqual(point.code_example, "```python\nx=1\n```")
        self.assertEqual(point.source, "Python-100-Days Day17")
        self.assertEqual(point.self_test, "手写 @timer")
        self.assertEqual(point.module, "M04")
        self.assertEqual(point.stage, 2)
        self.assertEqual(point.difficulty, 3)
        self.assertEqual(point.tags, ["高频面试", "八股"])

    def test_merged_includes_structured_fields(self):
        pid = self.all_ids()[0]
        self.repo.conn.execute(
            "UPDATE knowledge_points SET mechanism='机制' WHERE id=?", (pid,))
        self.repo.conn.commit()
        data = self.repo.merged(self.repo.get_point(pid), None)
        self.assertIn("mechanism", data)
        self.assertEqual(data["mechanism"], "机制")


class TestUpsertPoints(RepoTestCase):
    def item(self, **overrides) -> dict:
        base = {
            "name": "新知识点 Test Item",
            "category": "测试模块",
            "definition": "一句话定义",
            "mechanism": "原理机制",
            "key_point": "面试要点",
            "code_example": "```python\nprint(1)\n```",
            "visualization": "https://example.com",
            "tags": ["测试"],
            "source": "测试来源",
            "self_test": "自测动作",
            "module": "M99",
            "stage": 2,
            "difficulty": 3,
        }
        base.update(overrides)
        return base

    def test_insert_new(self):
        stats = self.repo.upsert_points([self.item()])
        self.assertEqual(stats, {"inserted": 1, "updated": 0, "unchanged": 0})

        point = next(p for p in self.repo.list_points() if p.name == "新知识点 Test Item")
        self.assertEqual(point.definition, "一句话定义")
        self.assertEqual(point.code_example, "```python\nprint(1)\n```")
        self.assertEqual(point.tags, ["测试"])
        self.assertEqual(point.stage, 2)
        self.assertEqual(point.difficulty, 3)

    def test_update_existing(self):
        self.repo.upsert_points([self.item()])
        stats = self.repo.upsert_points([self.item(mechanism="改过的机制")])
        self.assertEqual(stats["updated"], 1)
        self.assertEqual(stats["inserted"], 0)

        point = next(p for p in self.repo.list_points() if p.name == "新知识点 Test Item")
        self.assertEqual(point.mechanism, "改过的机制")

    def test_unchanged_detected(self):
        self.repo.upsert_points([self.item()])
        stats = self.repo.upsert_points([self.item()])
        self.assertEqual(stats, {"inserted": 0, "updated": 0, "unchanged": 1})

    def test_category_defaults_when_missing(self):
        self.repo.upsert_points([{"name": "无分类条目", "definition": "x"}])
        point = next(p for p in self.repo.list_points() if p.name == "无分类条目")
        self.assertEqual(point.category, "未分类")

    def test_skips_empty_name(self):
        stats = self.repo.upsert_points([{"name": "   ", "definition": "x"}])
        self.assertEqual(sum(stats.values()), 0)

    def test_learning_records_survive_update(self):
        pid = self.all_ids()[0]
        self.repo.mark_learned(pid, 2)
        name = self.repo.get_point(pid).name

        self.repo.upsert_points([self.item(name=name, definition="新定义")])

        record = self.repo.get_record(pid)
        self.assertIsNotNone(record, "更新内容不应影响学习记录")
        self.assertEqual(record.mastery, 2)
        self.assertEqual(self.repo.get_point(pid).definition, "新定义")


class TestRenamePoint(RepoTestCase):
    def test_rename_keeps_learning_record(self):
        pid = self.all_ids()[0]
        self.repo.mark_learned(pid, 3)
        old = self.repo.get_point(pid).name

        self.assertTrue(self.repo.rename_point(old, "改名后的知识点"))

        point = self.repo.get_point(pid)
        self.assertEqual(point.name, "改名后的知识点")
        self.assertEqual(self.repo.get_record(pid).mastery, 3, "改名不应丢学习进度")

    def test_rename_missing_returns_false(self):
        self.assertFalse(self.repo.rename_point("不存在的名字", "新名字"))

    def test_rename_to_taken_name_returns_false(self):
        ids = self.all_ids()
        first = self.repo.get_point(ids[0]).name
        second = self.repo.get_point(ids[1]).name
        self.assertFalse(self.repo.rename_point(first, second))
        self.assertEqual(self.repo.get_point(ids[0]).name, first, "冲突时不应改动")

    def test_rename_same_name_is_noop(self):
        pid = self.all_ids()[0]
        name = self.repo.get_point(pid).name
        self.assertFalse(self.repo.rename_point(name, name))


if __name__ == "__main__":
    unittest.main()
