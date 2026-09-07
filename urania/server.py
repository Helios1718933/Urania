"""HTTP 服务器装配（ThreadingHTTPServer，仅监听本机回环地址）。"""
from __future__ import annotations

from http.server import ThreadingHTTPServer

from . import config
from .api import make_handler
from .repository import KnowledgeRepository


def create_server(repo: KnowledgeRepository,
                  host: str = config.DEFAULT_HOST,
                  port: int | None = None) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer(
        (host, port if port is not None else config.DEFAULT_PORT),
        make_handler(repo),
    )
    httpd.daemon_threads = True
    return httpd
