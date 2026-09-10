"""测试公共夹具：临时目录中的独立数据库。"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from urania import db, seed
from urania.repository import KnowledgeRepository

TEST_ITEMS = [
    {"name": f"测试知识点{i}", "category": "Python 基础",
     "principle": f"第 {i} 条原理讲解。", "visualization": "", "tags": ["测试"]}
    for i in range(1, 11)
]


class RepoTestCase(unittest.TestCase):
    """每个测试用例使用独立的临时数据库并预置 10 个知识点。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "test.db"
        self.repo = KnowledgeRepository(db.init(self.db_path))
        seed.seed_if_needed(self.repo, TEST_ITEMS)

    def tearDown(self):
        self.repo.conn.close()
        self._tmp.cleanup()

    def all_ids(self):
        return [p.id for p in self.repo.list_points()]
