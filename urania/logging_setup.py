"""日志配置（默认人类可读，可用环境变量切 JSON 行）。

设计取舍：这是单人本地应用，终端里的可读性优先，所以默认输出普通文本；
同时所有日志都带结构化字段（通过 ``extra={"event": {...}}``），
需要接入日志系统时设 ``URANIA_LOG_JSON=1`` 即可切到 JSON 行格式。
"""
from __future__ import annotations

import json
import logging
import os
import sys

_TEXT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%H:%M:%S"


def _event_of(record: logging.LogRecord) -> dict | None:
    event = getattr(record, "event", None)
    return event if isinstance(event, dict) else None


class TextFormatter(logging.Formatter):
    """人类可读文本，结构化字段以 key=value 追加在行尾。"""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        event = _event_of(record)
        if event:
            kv = " ".join(f"{k}={v}" for k, v in event.items())
            base = f"{base} | {kv}"
        return base


class JsonFormatter(logging.Formatter):
    """每行一个 JSON 对象，便于被日志系统采集。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        event = _event_of(record)
        if event:
            payload.update(event)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: int = logging.INFO, json_output: bool | None = None) -> None:
    """配置根 logger（幂等，可重复调用）。"""
    if json_output is None:
        json_output = os.environ.get("URANIA_LOG_JSON", "").strip().lower() in {"1", "true", "yes"}

    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(TextFormatter(_TEXT_FORMAT, _DATE_FORMAT))

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)


def request_event(method: str, path: str, status: int, duration_ms: float,
                  size: int = 0) -> dict:
    """构造 HTTP 请求日志的结构化字段。"""
    return {
        "kind": "http",
        "method": method,
        "path": path,
        "status": status,
        "duration_ms": round(duration_ms, 1),
        "bytes": size,
    }
