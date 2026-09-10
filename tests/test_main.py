"""应用入口（main.py）测试：参数解析、端口探测、单实例锁、局域网地址。"""
from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from common import RepoTestCase

import main as app_main
from urania.server import create_server


class TestParseArgs(unittest.TestCase):
    def parse(self, argv):
        with mock.patch.object(sys, "argv", ["main.py", *argv]):
            return app_main.parse_args()

    def test_defaults(self):
        args = self.parse([])
        self.assertEqual(args.port, 8765)
        self.assertFalse(args.lan)
        self.assertFalse(args.browser)
        self.assertFalse(args.no_window)
        self.assertFalse(args.reset)

    def test_lan_and_port(self):
        args = self.parse(["--lan", "--port", "9000", "--no-window"])
        self.assertTrue(args.lan)
        self.assertEqual(args.port, 9000)
        self.assertTrue(args.no_window)

    def test_reset_flag(self):
        self.assertTrue(self.parse(["--reset"]).reset)


class TestLocalIP(unittest.TestCase):
    def test_returns_non_empty_string(self):
        ip = app_main.local_ip()
        self.assertIsInstance(ip, str)
        self.assertTrue(ip)
        parts = ip.split(".")
        self.assertEqual(len(parts), 4, f"应返回点分十进制地址，得到 {ip!r}")


class TestProbe(RepoTestCase):
    def test_closed_port_is_not_urania(self):
        # 选一个几乎不可能被占用的高位端口
        self.assertFalse(app_main.probe_running_instance(59999))

    def test_running_server_is_detected(self):
        httpd = create_server(self.repo, host="127.0.0.1", port=0)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            self.assertTrue(app_main.probe_running_instance(port))
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_pick_free_port_returns_requested_when_free(self):
        port = app_main.pick_free_port(59123, host="127.0.0.1")
        self.assertEqual(port, 59123)

    def test_pick_free_port_skips_existing_instance(self):
        httpd = create_server(self.repo, host="127.0.0.1", port=0)
        occupied = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            chosen = app_main.pick_free_port(occupied, host="127.0.0.1")
            self.assertNotEqual(chosen, occupied, "不应复用已有实例占用的端口")
        finally:
            httpd.shutdown()
            httpd.server_close()


class TestInstanceLock(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.lock_path = Path(self._tmp.name) / "urania.lock"
        self._patcher = mock.patch.object(app_main, "LOCK_PATH", self.lock_path)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._tmp.cleanup()

    def test_first_acquire_gets_lock(self):
        fh, port = app_main.acquire_instance_lock()
        self.assertIsNotNone(fh)
        self.assertIsNone(port, "拿锁时还没有端口可读")
        fh.close()

    def test_second_acquire_reads_port_and_fails(self):
        first, _ = app_main.acquire_instance_lock()
        assert first is not None
        app_main.write_port_to_lock(first, 8765)
        try:
            second, port = app_main.acquire_instance_lock()
            self.assertIsNone(second, "同一文件描述符已被占用，应拿不到锁")
            self.assertEqual(port, 8765, "拿不到锁时应读到运行实例写入的端口")
        finally:
            first.close()

    def test_lock_is_released_after_close(self):
        first, _ = app_main.acquire_instance_lock()
        assert first is not None
        app_main.write_port_to_lock(first, 8765)
        first.close()

        again, port = app_main.acquire_instance_lock()
        self.assertIsNotNone(again, "释放后应能重新拿锁")
        self.assertIsNone(port, "重新拿锁后应清掉历史端口")
        again.close()

    def test_write_port_overwrites_previous(self):
        fh, _ = app_main.acquire_instance_lock()
        assert fh is not None
        app_main.write_port_to_lock(fh, 8080)
        app_main.write_port_to_lock(fh, 9001)
        self.assertEqual(self.lock_path.read_text(encoding="utf-8").strip(), "9001",
                         "锁文件里应只保留最新端口")
        fh.close()


if __name__ == "__main__":
    unittest.main()
