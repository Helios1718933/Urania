"""访问令牌（``--lan`` 模式的认证）。

设计
----
- 令牌持久化在 ``DATA_DIR/.token``（0600 权限），首次以 ``--lan`` 启动时自动生成
- 客户端两种方式任一通过认证：
  1. 首次访问带 ``?token=xxx`` → 服务端写入 HttpOnly Cookie 并 302 重定向，
     令牌从地址栏消失；之后手机浏览器直接打开根路径即可
  2. 请求头 ``Authorization: Bearer xxx``（curl / 脚本友好）
- 令牌即密码；比较用 ``hmac.compare_digest``（定时安全）
- 认证失败时暂停一小段，抬高在线暴力猜测的成本

安全边界：本模块只服务于「家庭局域网内单人使用」的场景；
若要暴露到公网，必须再加 HTTPS 与更严格的口令策略。
"""
from __future__ import annotations

import hmac
import secrets
import time
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs

COOKIE_NAME = "urania_token"
COOKIE_MAX_AGE = 365 * 24 * 3600  # 一年
TOKEN_LENGTH = 8
# 去掉易混字符（0/O、1/l/I），方便在手机上手输
_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
FAILURE_DELAY_SECONDS = 0.5


def generate_token() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(TOKEN_LENGTH))


def load_or_create_token(path: Path) -> str:
    """读取令牌；不存在则生成并落盘（0600）。"""
    if path.exists():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    token = generate_token()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:  # 某些文件系统不支持 chmod，忽略
        pass
    return token


def constant_time_equals(candidate: str | None, expected: str) -> bool:
    if not candidate:
        return False
    return hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8"))


def token_from_header(header_value: str | None) -> str | None:
    """从 ``Authorization: Bearer xxx`` 中取令牌。"""
    if not header_value:
        return None
    parts = header_value.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def token_from_cookie(cookie_header: str | None) -> str | None:
    """从 Cookie 中取令牌。"""
    if not cookie_header:
        return None
    try:
        jar = SimpleCookie()
        jar.load(cookie_header)
    except Exception:  # noqa: BLE001 畸形的 Cookie 头不应导致 500
        return None
    morsel = jar.get(COOKIE_NAME)
    return morsel.value if morsel else None


def token_from_query(query: str) -> str | None:
    """从查询串 ``?token=xxx`` 中取令牌。"""
    values = parse_qs(query).get("token")
    return values[0] if values else None


def slow_down_failure() -> None:
    """认证失败时短暂停顿，抬高暴力猜测成本。"""
    time.sleep(FAILURE_DELAY_SECONDS)


LOGIN_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="color-scheme" content="light dark">
  <title>Urania · 需要访问口令</title>
  <style>
    :root { color-scheme: light dark; }
    body {
      margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
      background: #f5f5f7; color: #1d1d1f; padding: 24px;
    }
    @media (prefers-color-scheme: dark) { body { background: #1e1e22; color: #f5f5f7; } }
    .card {
      width: 100%; max-width: 360px; background: #fff; border-radius: 16px;
      padding: 28px 24px; box-shadow: 0 1px 3px rgba(0,0,0,.08), 0 12px 32px rgba(0,0,0,.08);
      text-align: center;
    }
    @media (prefers-color-scheme: dark) { .card { background: #2c2c2e; } }
    h1 { font-size: 20px; margin: 0 0 6px; }
    p { font-size: 13px; opacity: .6; margin: 0 0 20px; line-height: 1.6; }
    input {
      width: 100%; box-sizing: border-box; font: inherit; font-size: 17px;
      padding: 12px 14px; border-radius: 10px; border: 1px solid rgba(120,120,128,.3);
      background: rgba(120,120,128,.08); color: inherit; text-align: center;
      letter-spacing: 2px; margin-bottom: 12px;
    }
    button {
      width: 100%; font: inherit; font-size: 15px; font-weight: 600;
      padding: 12px; border: 0; border-radius: 10px; background: #007aff; color: #fff;
      cursor: pointer;
    }
    button:active { opacity: .8; }
    .error { color: #ff3b30; font-size: 13px; margin-bottom: 12px; min-height: 18px; }
  </style>
</head>
<body>
  <form class="card" method="get" action="/">
    <h1>Urania</h1>
    <p>局域网模式已开启<br>请输入启动时终端显示的口令</p>
    <div class="error">{error}</div>
    <input name="token" autocomplete="off" autocapitalize="off" autocorrect="off"
           spellcheck="false" placeholder="访问口令" autofocus>
    <button type="submit">进入</button>
  </form>
</body>
</html>
"""
