"""访问令牌（--lan 模式认证）测试。"""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from common import RepoTestCase
from urania import auth, db, seed
from urania.repository import KnowledgeRepository
from urania.server import create_server

TOKEN = "testtokn"


class TestTokenHelpers(unittest.TestCase):
    def test_generated_token_is_typed_friendly(self):
        for _ in range(20):
            token = auth.generate_token()
            self.assertEqual(len(token), auth.TOKEN_LENGTH)
            self.assertTrue(all(ch in auth._ALPHABET for ch in token))
            for ambiguous in "01lo":
                self.assertNotIn(ambiguous, token, "不应包含易混字符")

    def test_tokens_are_random(self):
        self.assertNotEqual({auth.generate_token() for _ in range(50)}.__len__(),
                            1, "令牌应随机生成")

    def test_load_or_create_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".token"
            first = auth.load_or_create_token(path)
            self.assertTrue(path.exists())
            self.assertEqual(auth.load_or_create_token(path), first, "第二次应读到同一个")

    def test_constant_time_equals(self):
        self.assertTrue(auth.constant_time_equals("abc", "abc"))
        self.assertFalse(auth.constant_time_equals("abc", "abd"))
        self.assertFalse(auth.constant_time_equals("", "abc"))
        self.assertFalse(auth.constant_time_equals(None, "abc"))

    def test_token_from_header(self):
        self.assertEqual(auth.token_from_header("Bearer abc123"), "abc123")
        self.assertEqual(auth.token_from_header("bearer abc123"), "abc123")
        self.assertIsNone(auth.token_from_header("Basic abc123"))
        self.assertIsNone(auth.token_from_header(None))

    def test_token_from_cookie(self):
        self.assertEqual(auth.token_from_cookie("urania_token=abc123"), "abc123")
        self.assertEqual(
            auth.token_from_cookie("other=1; urania_token=xyz; more=2"), "xyz")
        self.assertIsNone(auth.token_from_cookie("other=1"))
        self.assertIsNone(auth.token_from_cookie(None))

    def test_token_from_query(self):
        self.assertEqual(auth.token_from_query("token=abc"), "abc")
        self.assertEqual(auth.token_from_query("a=1&token=abc&b=2"), "abc")
        self.assertIsNone(auth.token_from_query("a=1"))


class AuthServerTestCase(RepoTestCase):
    """带认证的服务器夹具。"""

    def setUp(self):
        super().setUp()
        self._tmp_token = tempfile.TemporaryDirectory()
        self.token_path = Path(self._tmp_token.name) / ".token"
        self.token = auth.load_or_create_token(self.token_path)

        # 测试里不要真的睡
        self._orig_delay = auth.FAILURE_DELAY_SECONDS
        auth.FAILURE_DELAY_SECONDS = 0

        self.httpd = create_server(
            self.repo, host="127.0.0.1", port=0, auth_token=self.token)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        auth.FAILURE_DELAY_SECONDS = self._orig_delay
        self._tmp_token.cleanup()
        super().tearDown()

    def request(self, path, method="GET", token=None, cookie=None, header=None):
        req = urllib.request.Request(self.base + path, method=method)
        if header:
            req.add_header("Authorization", header)
        if cookie:
            req.add_header("Cookie", cookie)
        try:
            with urllib.request.urlopen(req) as resp:
                body = resp.read().decode()
                try:
                    return resp.status, json.loads(body), dict(resp.headers)
                except json.JSONDecodeError:
                    return resp.status, body, dict(resp.headers)
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            try:
                return e.code, json.loads(body), dict(e.headers)
            except json.JSONDecodeError:
                return e.code, body, dict(e.headers)


class TestAuthEnforcement(AuthServerTestCase):
    def test_health_is_open(self):
        status, data, _ = self.request("/api/health")
        self.assertEqual(status, 200, "单实例探测依赖 health，必须免认证")
        self.assertEqual(data["app"], "Urania")

    def test_api_without_token_is_401(self):
        status, data, _ = self.request("/api/stats")
        self.assertEqual(status, 401)
        self.assertIn("error", data)

    def test_api_with_wrong_token_is_401(self):
        status, _, _ = self.request("/api/stats", header="Bearer wrongtoken")
        self.assertEqual(status, 401)

    def test_api_with_bearer_header_ok(self):
        status, data, _ = self.request("/api/stats", header=f"Bearer {self.token}")
        self.assertEqual(status, 200)
        self.assertIn("total", data)

    def test_api_with_cookie_ok(self):
        status, _, _ = self.request("/api/stats", cookie=f"urania_token={self.token}")
        self.assertEqual(status, 200)

    def test_root_without_token_shows_login_page(self):
        status, body, headers = self.request("/")
        self.assertEqual(status, 401)
        self.assertIn("访问口令", body)
        self.assertIn("text/html", headers.get("Content-Type", ""))

    def test_static_assets_require_auth(self):
        status, _, _ = self.request("/js/app.js")
        self.assertEqual(status, 401, "静态资源也应对未认证者隐藏")

    def test_query_token_sets_cookie_and_redirects(self):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None      # 阻止自动跟随，便于断言 302
        opener = urllib.request.build_opener(NoRedirect)
        req = urllib.request.Request(f"{self.base}/?token={self.token}")
        try:
            with opener.open(req) as resp:
                status, headers = resp.status, dict(resp.headers)
        except urllib.error.HTTPError as e:
            status, headers = e.code, dict(e.headers)

        self.assertEqual(status, 302)
        self.assertEqual(headers.get("Location"), "/", "重定向后 URL 不应再带令牌")
        self.assertIn("urania_token=", headers.get("Set-Cookie", ""))
        self.assertIn("HttpOnly", headers.get("Set-Cookie", ""))

    def test_wrong_query_token_shows_login_with_error(self):
        status, body, _ = self.request("/?token=nope")
        self.assertEqual(status, 401)
        self.assertIn("不正确", body)

    def test_bearer_token_does_not_need_cookie(self):
        """脚本/curl 场景：只给 Bearer 头也能用。"""
        status, _, _ = self.request("/api/config", header=f"Bearer {self.token}")
        self.assertEqual(status, 200)


class TestAuthDisabled(RepoTestCase):
    """默认模式（未开 --lan）不应要求认证，保证向后兼容。"""

    def setUp(self):
        super().setUp()
        self.httpd = create_server(self.repo, host="127.0.0.1", port=0)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        super().tearDown()

    def test_default_mode_needs_no_auth(self):
        for path in ("/", "/api/stats", "/js/app.js"):
            with self.subTest(path=path):
                with urllib.request.urlopen(self.base + path) as resp:
                    self.assertEqual(resp.status, 200)


if __name__ == "__main__":
    unittest.main()
