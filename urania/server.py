"""HTTP 服务器装配（ThreadingHTTPServer）。

默认只监听本机回环地址；``--lan`` 模式监听 ``0.0.0.0`` 并强制要求访问令牌
（见 ``urania/auth.py``）。
"""
from __future__ import annotations

from http.server import ThreadingHTTPServer

from . import config
from .api import make_handler
from .repository import KnowledgeRepository


def create_server(
    repo: KnowledgeRepository,
    host: str = config.DEFAULT_HOST,
    port: int | None = None,
    auth_token: str | None = None,
) -> ThreadingHTTPServer:
    """装配服务器。

    Args:
        repo: 数据仓库。
        host: 监听地址；``0.0.0.0`` 表示局域网可访问。
        port: 端口；None 用默认值，0 表示由系统分配（测试用）。
        auth_token: 非 None 时启用令牌认证（局域网模式必须传）。
    """
    httpd = ThreadingHTTPServer(
        (host, port if port is not None else config.DEFAULT_PORT),
        make_handler(repo, auth_token=auth_token),
    )
    httpd.daemon_threads = True
    return httpd
