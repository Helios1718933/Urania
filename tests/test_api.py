"""HTTP API 端到端测试（真实起一个临时端口的 HTTPServer）。"""
from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request

from common import RepoTestCase
from urania.server import create_server


class TestAPI(RepoTestCase):
    def setUp(self):
        super().setUp()
        self.httpd = create_server(self.repo, host="127.0.0.1", port=0)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        super().tearDown()

    def request(self, path, method="GET", body=None):
        req = urllib.request.Request(
            self.base + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def test_health(self):
        status, data = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")

    def test_draw_and_mark_learned_flow(self):
        status, data = self.request("/api/draw")
        self.assertEqual(status, 200)
        point = data["point"]
        self.assertIsNotNone(point)
        self.assertEqual(data["remaining"], 10)  # 抽取本身不改变状态

        status, data = self.request(f"/api/points/{point['id']}/learn",
                                    method="POST", body={"mastery": 2})
        self.assertEqual(status, 200)
        self.assertEqual(data["point"]["mastery"], 2)

        # 已学习的不再出现在抽取结果中，剩余数减一
        for _ in range(30):
            _, d = self.request("/api/draw")
            self.assertNotEqual(d["point"]["id"], point["id"])
        self.assertEqual(d["remaining"], 9)

    def test_review_rating_flow(self):
        _, data = self.request("/api/draw")
        pid = data["point"]["id"]
        self.request(f"/api/points/{pid}/learn", method="POST", body={"mastery": 3})

        status, data = self.request(f"/api/points/{pid}/review",
                                    method="POST", body={"rating": "solid"})
        self.assertEqual(status, 200)
        self.assertEqual(data["point"]["mastery"], 4)
        self.assertEqual(data["point"]["status"], "mastered")

    def test_review_bad_rating_rejected(self):
        _, data = self.request("/api/draw")
        pid = data["point"]["id"]
        self.request(f"/api/points/{pid}/learn", method="POST", body={"mastery": 1})
        status, _ = self.request(f"/api/points/{pid}/review",
                                 method="POST", body={"rating": "great"})
        self.assertEqual(status, 400)

    def test_review_without_record_404(self):
        status, _ = self.request("/api/points/1/review", method="POST", body={"rating": "solid"})
        self.assertEqual(status, 404)

    def test_reset_record(self):
        _, data = self.request("/api/draw")
        pid = data["point"]["id"]
        self.request(f"/api/points/{pid}/learn", method="POST", body={"mastery": 1})
        status, _ = self.request(f"/api/points/{pid}/record", method="DELETE")
        self.assertEqual(status, 200)
        # 又能被抽到了
        for _ in range(30):
            _, d = self.request("/api/draw")
            if d["point"]["id"] == pid:
                break
        else:
            self.fail("重置后的知识点未能重新被抽中")

    def test_review_queue_and_stats(self):
        _, data = self.request("/api/draw")
        pid = data["point"]["id"]
        self.request(f"/api/points/{pid}/learn", method="POST", body={"mastery": 2})

        status, q = self.request("/api/review/queue")
        self.assertEqual(status, 200)
        self.assertEqual(len(q["items"]), 1)
        self.assertTrue(q["items"][0]["is_due"])  # 刚标记，今天该复习

        status, s = self.request("/api/stats")
        self.assertEqual(status, 200)
        self.assertEqual(s["unlearned"], 9)

    def test_add_point_via_api(self):
        status, data = self.request("/api/points", method="POST", body={
            "name": "API 新增知识点", "category": "工程实践",
            "principle": "通过 API 添加", "visualization": "https://example.com",
            "tags": ["api"],
        })
        self.assertEqual(status, 201)
        self.assertEqual(data["point"]["status"], "unlearned")

    def test_static_index(self):
        with urllib.request.urlopen(self.base + "/") as resp:
            html = resp.read().decode()
        self.assertIn("Urania", html)

    def test_static_traversal_blocked(self):
        status, _ = self.request("/css/../urania/config.py")
        self.assertEqual(status, 404)

    def test_export_endpoint(self):
        _, data = self.request("/api/draw")
        pid = data["point"]["id"]
        self.request(f"/api/points/{pid}/learn", method="POST", body={"mastery": 2})
        self.request(f"/api/points/{pid}/review", method="POST", body={"rating": "solid"})

        status, payload = self.request("/api/export")
        self.assertEqual(status, 200)
        self.assertEqual(set(payload) & {"knowledge_points", "learning_records", "review_logs"},
                         {"knowledge_points", "learning_records", "review_logs"})
        self.assertEqual(len(payload["learning_records"]), 1)
        self.assertEqual(len(payload["review_logs"]), 2)
        self.assertEqual(payload["meta"]["app"], "Urania")
        self.assertIn("schema_version", payload["meta"])

    def test_review_writes_log_not_just_counter(self):
        """复习后除计数外，历史日志也应落库（接口层验证）。"""
        _, data = self.request("/api/draw")
        pid = data["point"]["id"]
        self.request(f"/api/points/{pid}/learn", method="POST", body={"mastery": 1})
        self.request(f"/api/points/{pid}/review", method="POST", body={"rating": "fuzzy"})

        _, payload = self.request("/api/export")
        sources = [row["source"] for row in payload["review_logs"]]
        self.assertEqual(sorted(sources), ["learn", "review"])

    # ------------------------------------------------ 错误契约（状态码一致性）--

    def test_learn_on_missing_point_returns_404(self):
        status, _ = self.request("/api/points/999999/learn",
                                 method="POST", body={"mastery": 1})
        self.assertEqual(status, 404, "知识点不存在应是 404，而不是 400")

    def test_duplicate_add_returns_409(self):
        _, data = self.request("/api/draw")
        name = data["point"]["name"]
        status, payload = self.request("/api/points", method="POST",
                                       body={"name": name, "category": "测试"})
        self.assertEqual(status, 409)
        self.assertIn("已存在", payload["error"])

    def test_empty_name_returns_400(self):
        status, _ = self.request("/api/points", method="POST", body={"name": "   "})
        self.assertEqual(status, 400)

    def test_non_integer_mastery_returns_400_not_500(self):
        _, data = self.request("/api/draw")
        pid = data["point"]["id"]
        status, _ = self.request(f"/api/points/{pid}/learn",
                                 method="POST", body={"mastery": "abc"})
        self.assertEqual(status, 400, "非法数字应是 400，不能被当成服务器错误")

    def test_invalid_json_body_returns_400(self):
        req = urllib.request.Request(
            self.base + "/api/points", method="POST",
            data=b"{not json", headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
        self.assertEqual(status, 400)

    def test_reset_missing_point_returns_404(self):
        status, _ = self.request("/api/points/999999/record", method="DELETE")
        self.assertEqual(status, 404)

    def test_reset_without_record_is_idempotent(self):
        _, data = self.request("/api/draw")
        pid = data["point"]["id"]          # 未学习，无记录
        status, payload = self.request(f"/api/points/{pid}/record", method="DELETE")
        self.assertEqual(status, 200)
        self.assertFalse(payload["removed"], "本来就没有记录，应如实返回 removed=false")

    def test_reset_existing_record_reports_removed(self):
        _, data = self.request("/api/draw")
        pid = data["point"]["id"]
        self.request(f"/api/points/{pid}/learn", method="POST", body={"mastery": 1})
        status, payload = self.request(f"/api/points/{pid}/record", method="DELETE")
        self.assertEqual(status, 200)
        self.assertTrue(payload["removed"])

    def test_unexpected_error_hides_internals(self):
        """500 不能回显异常原文，只给错误编号。"""
        def boom(*args, **kwargs):
            raise RuntimeError("内部细节：SELECT * FROM secret_table")

        original = self.repo.stats
        self.repo.stats = boom  # type: ignore[method-assign]
        try:
            status, payload = self.request("/api/stats")
        finally:
            self.repo.stats = original  # type: ignore[method-assign]

        self.assertEqual(status, 500)
        self.assertNotIn("secret_table", payload["error"], "不能泄漏内部细节")
        self.assertNotIn("Traceback", payload["error"])
        self.assertIn("错误编号", payload["error"])

    def test_request_is_logged(self):
        with self.assertLogs("urania.api", level="INFO") as captured:
            self.request("/api/health")
        self.assertTrue(
            any("GET /api/health" in line for line in captured.output),
            "每个请求都应留下访问日志",
        )

    def test_business_error_is_logged(self):
        with self.assertLogs("urania.api", level="INFO") as captured:
            self.request("/api/points/999999")
        self.assertTrue(any("NotFoundError" in line for line in captured.output))


if __name__ == "__main__":
    unittest.main()
