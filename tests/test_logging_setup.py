"""日志配置测试（文本 / JSON 两种格式与结构化字段）。"""
from __future__ import annotations

import json
import logging
import unittest

from urania import logging_setup


class TestFormatters(unittest.TestCase):
    def make_record(self, event=None, exc_info=None):
        record = logging.LogRecord(
            name="urania.test", level=logging.INFO, pathname=__file__, lineno=1,
            msg="测试消息 %s", args=("参数",), exc_info=exc_info,
        )
        if event is not None:
            record.event = event
        return record

    def test_text_formatter_appends_event_as_key_value(self):
        fmt = logging_setup.TextFormatter("%(message)s", "%H:%M:%S")
        out = fmt.format(self.make_record(event={"kind": "http", "status": 200}))
        self.assertIn("测试消息 参数", out)
        self.assertIn("kind=http", out)
        self.assertIn("status=200", out)

    def test_text_formatter_without_event(self):
        fmt = logging_setup.TextFormatter("%(message)s", "%H:%M:%S")
        out = fmt.format(self.make_record())
        self.assertEqual(out, "测试消息 参数")
        self.assertNotIn("|", out)

    def test_json_formatter_is_one_json_object(self):
        fmt = logging_setup.JsonFormatter()
        out = fmt.format(self.make_record(event={"kind": "http", "status": 404}))
        payload = json.loads(out)
        self.assertEqual(payload["msg"], "测试消息 参数")
        self.assertEqual(payload["level"], "INFO")
        self.assertEqual(payload["logger"], "urania.test")
        self.assertEqual(payload["kind"], "http")
        self.assertEqual(payload["status"], 404)
        self.assertIn("ts", payload)

    def test_json_formatter_keeps_traceback(self):
        fmt = logging_setup.JsonFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            record = self.make_record(exc_info=sys.exc_info())
        payload = json.loads(fmt.format(record))
        self.assertIn("boom", payload["exception"])
        self.assertIn("Traceback", payload["exception"])

    def test_non_dict_event_is_ignored(self):
        fmt = logging_setup.TextFormatter("%(message)s", "%H:%M:%S")
        record = self.make_record()
        record.event = "不是字典"
        self.assertEqual(fmt.format(record), "测试消息 参数")


class TestSetup(unittest.TestCase):
    def setUp(self):
        self._root = logging.getLogger()
        self._saved = self._root.handlers[:]
        self._level = self._root.level

    def tearDown(self):
        self._root.handlers[:] = self._saved
        self._root.setLevel(self._level)

    def test_setup_installs_single_handler(self):
        logging_setup.setup_logging()
        self.assertEqual(len(self._root.handlers), 1, "重复调用不应叠加 handler")

    def test_setup_is_idempotent(self):
        logging_setup.setup_logging()
        logging_setup.setup_logging()
        self.assertEqual(len(self._root.handlers), 1)

    def test_json_output_switch(self):
        logging_setup.setup_logging(json_output=True)
        self.assertIsInstance(self._root.handlers[0].formatter, logging_setup.JsonFormatter)

        logging_setup.setup_logging(json_output=False)
        self.assertIsInstance(self._root.handlers[0].formatter, logging_setup.TextFormatter)

    def test_env_var_enables_json(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"URANIA_LOG_JSON": "1"}):
            logging_setup.setup_logging()
        self.assertIsInstance(self._root.handlers[0].formatter, logging_setup.JsonFormatter)

    def test_request_event_shape(self):
        event = logging_setup.request_event("GET", "/api/stats", 200, 1.23456, 128)
        self.assertEqual(event["kind"], "http")
        self.assertEqual(event["method"], "GET")
        self.assertEqual(event["path"], "/api/stats")
        self.assertEqual(event["status"], 200)
        self.assertEqual(event["duration_ms"], 1.2, "耗时保留一位小数")
        self.assertEqual(event["bytes"], 128)


if __name__ == "__main__":
    unittest.main()
