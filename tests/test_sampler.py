"""核心功能：随机抽取 未标注（未学习）知识点。"""
from __future__ import annotations

import random
import unittest
from collections import Counter

from common import RepoTestCase

from urania.models import KnowledgePoint
from urania.sampler import draw_unlearned


def _points(n):
    return [KnowledgePoint(id=i, name=f"p{i}", category="c", principle="") for i in range(n)]


class TestSampler(unittest.TestCase):
    def test_empty_returns_none(self):
        self.assertIsNone(draw_unlearned([]))

    def test_returns_member_of_candidates(self):
        pts = _points(5)
        for _ in range(20):
            self.assertIn(draw_unlearned(pts).id, {p.id for p in pts})

    def test_roughly_uniform(self):
        pts = _points(5)
        rng = random.Random(42)
        counts = Counter(draw_unlearned(pts, rng=rng).id for _ in range(5000))
        # 每个知识点被抽中的频率应接近 1/5（宽松断言避免偶发失败）
        for i in range(5):
            self.assertGreater(counts[i], 5000 / 5 * 0.7)

    def test_seed_reproducible(self):
        pts = _points(50)
        a = draw_unlearned(pts, rng=random.Random(1))
        b = draw_unlearned(pts, rng=random.Random(1))
        self.assertEqual(a.id, b.id)


class TestDrawOnlyUnlearned(RepoTestCase):
    def test_draw_excludes_learned(self):
        first = draw_unlearned(self.repo.unlearned_points())
        self.repo.mark_learned(first.id, 2)
        # 疯狂抽 200 次，已学习的那条绝不该再出现
        for _ in range(200):
            p = draw_unlearned(self.repo.unlearned_points())
            self.assertIsNotNone(p)
            self.assertNotEqual(p.id, first.id)

    def test_all_learned_returns_none(self):
        for p in self.repo.list_points():
            self.repo.mark_learned(p.id, 1)
        self.assertIsNone(draw_unlearned(self.repo.unlearned_points()))


if __name__ == "__main__":
    unittest.main()
