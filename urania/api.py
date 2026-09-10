"""REST API + 前端静态文件服务（标准库 http.server，零依赖）。

路由一览：
    GET    /api/health                 存活检查
    GET    /api/config                 前端需要的领域常量（掌握度标签、自评档位）
    GET    /api/stats                  学习统计
    GET    /api/draw                   随机抽取一个未学习知识点（核心功能，不改变状态）
    GET    /api/export                 导出全库（知识点 + 学习记录 + 复习日志 + 元信息）
    POST   /api/points                 新增知识点 {name, category, principle, visualization, tags}
    GET    /api/points                 全部知识点（含学习状态）
    GET    /api/points/{id}            知识点详情
    POST   /api/points/{id}/learn      标记已学习 {mastery: 1~3}
    POST   /api/points/{id}/review     提交一次复习自评 {rating: forgot|fuzzy|solid}
    DELETE /api/points/{id}/record     删除学习记录（重置为未学习）
    GET    /api/review/queue           复习队列（到期优先，按掌握度升序）

错误约定
--------
- 业务错误：``RepositoryError`` 的子类自带 ``status``（400 / 404 / 409），原样透传给客户端。
- 未预期异常：记录完整堆栈到服务端日志，只回一个**带错误编号**的通用 500，
  **不回显异常原文**（避免泄漏 SQL 片段与文件路径）。
"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

from . import auth, config, migrations, sampler
from .logging_setup import request_event
from .repository import KnowledgeRepository, RepositoryError, ValidationError
from .review import RATING_LABELS, RATINGS

logger = logging.getLogger("urania.api")

_STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


def make_handler(repo: KnowledgeRepository, auth_token: str | None = None):
    """构建请求处理器。

    Args:
        repo: 数据仓库。
        auth_token: 非 None 时启用访问令牌认证（局域网模式）。
            ``/api/health`` 始终免认证——单实例探测依赖它（它只暴露应用名与版本）。
    """
    class UraniaRequestHandler(BaseHTTPRequestHandler):
        server_version = f"Urania/{config.APP_VERSION}"
        protocol_version = "HTTP/1.1"

        # ------------------------------------------------------------ 日志 --
        def log_message(self, fmt, *args) -> None:
            """屏蔽基类往 stderr 裸打的日志——请求日志改由 _send 统一输出。"""

        def log_error(self, fmt, *args) -> None:
            logger.warning("HTTP 协议层错误: %s", fmt % args)

        def handle_one_request(self) -> None:
            self._started_at = time.perf_counter()
            super().handle_one_request()

        def _log_request(self, status: int, size: int) -> None:
            started = getattr(self, "_started_at", None)
            duration_ms = (time.perf_counter() - started) * 1000 if started else 0.0
            method = getattr(self, "command", "-")
            path = urlparse(getattr(self, "path", "")).path
            logger.info(
                "%s %s → %s (%.1fms)", method, path, status, duration_ms,
                extra={"event": request_event(method, path, status, duration_ms, size)},
            )

        # -------------------------------------------------------- 工具方法 --
        def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header(
                "Cache-Control",
                "no-store" if content_type.startswith("application/json") else "no-cache",
            )
            self.end_headers()
            self.wfile.write(body)
            self._log_request(status, len(body))

        def _json(self, obj, status: int = 200) -> None:
            self._send(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8", status)

        def _error(self, status: int, message: str) -> None:
            self._json({"error": message}, status)

        def _repo_error(self, exc: RepositoryError) -> None:
            """业务错误：按异常自带的状态码透传。"""
            status = getattr(exc, "status", 400)
            logger.info("业务错误 %s(%s): %s", type(exc).__name__, status, exc)
            self._error(status, str(exc))

        def _internal_error(self, exc: Exception) -> None:
            """未预期异常：服务端留堆栈，客户端只拿到错误编号。"""
            error_id = uuid.uuid4().hex[:8]
            logger.exception(
                "请求处理失败 [%s] %s %s", error_id,
                getattr(self, "command", "-"), getattr(self, "path", "-"),
            )
            self._error(500, f"服务器内部错误（错误编号 {error_id}），详情见服务端日志")

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length == 0:
                return {}
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ValidationError("请求体不是合法的 JSON") from exc

        # ------------------------------------------------------------ 认证 --
        def _check_auth(self) -> bool:
            """认证通过返回 True；已响应（登录页/跳转/401）返回 False。"""
            if auth_token is None:
                return True

            parsed = urlparse(self.path)
            if parsed.path == "/api/health":     # 单实例探测依赖，保持开放
                return True

            # 1) 地址栏带 ?token=xxx：校验通过后写 Cookie 并跳转（令牌从 URL 消失）
            query_token = auth.token_from_query(parsed.query)
            if query_token is not None:
                if auth.constant_time_equals(query_token, auth_token):
                    self._redirect_with_cookie(parsed)
                    return False
                auth.slow_down_failure()
                self._send_login_page("口令不正确，请重新输入")
                return False

            # 2) Cookie 或 Authorization 头
            candidate = (
                auth.token_from_cookie(self.headers.get("Cookie"))
                or auth.token_from_header(self.headers.get("Authorization"))
            )
            if auth.constant_time_equals(candidate, auth_token):
                return True

            # 3) 未通过
            auth.slow_down_failure()
            if parsed.path.startswith("/api/") or parsed.path.startswith(("/css/", "/js/")):
                self._error(401, "未通过认证：请先在浏览器打开根路径输入访问口令")
            else:
                self._send_login_page("")
            return False

        def _redirect_with_cookie(self, parsed) -> None:
            """写入令牌 Cookie 并 302 到不带 token 参数的地址。"""
            target = parsed.path or "/"
            remaining = [p for p in parsed.query.split("&") if p and not p.startswith("token=")]
            if remaining:
                target = f"{target}?{'&'.join(remaining)}"
            self.send_response(302)
            self.send_header("Location", target)
            self.send_header(
                "Set-Cookie",
                f"{auth.COOKIE_NAME}={auth_token}; Path=/; Max-Age={auth.COOKIE_MAX_AGE};"
                " HttpOnly; SameSite=Lax",
            )
            self.send_header("Content-Length", "0")
            self.end_headers()
            self._log_request(302, 0)

        def _send_login_page(self, error: str) -> None:
            body = auth.LOGIN_PAGE.replace("{error}", error).encode("utf-8")
            self._send(body, "text/html; charset=utf-8", 401)

        def _static(self, rel: str) -> None:
            """安全地返回 frontend/ 下的静态文件。"""
            base = config.FRONTEND_DIR.resolve()
            target = (base / rel).resolve()
            if not str(target).startswith(str(base)) or target.suffix not in _STATIC_TYPES:
                self._error(404, "文件不存在")
                return
            if not target.is_file():
                self._error(404, "文件不存在")
                return
            self._send(target.read_bytes(), _STATIC_TYPES[target.suffix])

        # ------------------------------------------------------------ 路由 --
        def do_GET(self):
            if not self._check_auth():
                return
            path = urlparse(self.path).path
            try:
                if path in ("/", "/index.html"):
                    self._static("index.html")
                elif path in ("/manifest.webmanifest", "/favicon.ico") or path.startswith(("/css/", "/js/", "/assets/")):
                    self._static(path.lstrip("/"))
                elif path == "/api/health":
                    self._json({"status": "ok", "app": config.APP_NAME,
                                "version": config.APP_VERSION})
                elif path == "/api/config":
                    self._json({
                        "app_name": config.APP_NAME,
                        "version": config.APP_VERSION,
                        "mastery_labels": {str(k): v for k, v in config.MASTERY_LABELS.items()},
                        "status_labels": config.STATUS_LABELS,
                        "rating_labels": RATING_LABELS,
                        "categories": config.DEFAULT_CATEGORIES,
                    })
                elif path == "/api/stats":
                    self._json(repo.stats())
                elif path == "/api/draw":
                    candidates = repo.unlearned_points()   # 只查一次
                    point = sampler.draw_unlearned(candidates)
                    self._json({"point": repo.merged(point, None) if point else None,
                                "remaining": len(candidates)})
                elif path == "/api/export":
                    payload = repo.export_all()
                    payload["meta"] = {
                        "app": config.APP_NAME,
                        "app_version": config.APP_VERSION,
                        "schema_version": migrations.current_version(repo.conn),
                        "exported_at": datetime.now().isoformat(timespec="seconds"),
                    }
                    self._json(payload)
                elif path == "/api/points":
                    self._json({"items": [repo.merged(p, repo.get_record(p.id))
                                          for p in repo.list_points()]})
                elif path == "/api/review/queue":
                    today = date.today().isoformat()
                    items = [repo.merged(p, r) for p, r in repo.learned_with_records()]
                    items.sort(key=lambda x: (not x["is_due"], x["next_review_at"] or "",
                                              x["mastery"]))
                    self._json({"items": items, "today": today})
                else:
                    m = re.fullmatch(r"/api/points/(\d+)", path)
                    if m:
                        p = repo.get_point(int(m.group(1)))
                        self._json({"point": repo.merged(p, repo.get_record(p.id))})
                    else:
                        self._error(404, "接口不存在")
            except RepositoryError as e:
                self._repo_error(e)
            except Exception as e:
                self._internal_error(e)

        def do_POST(self):
            if not self._check_auth():
                return
            path = urlparse(self.path).path
            try:
                m = re.fullmatch(r"/api/points/(\d+)/learn", path)
                if m:
                    point_id = int(m.group(1))
                    mastery = self._parse_int(self._body().get("mastery", 1), "mastery")
                    repo.mark_learned(point_id, mastery)
                    p = repo.get_point(point_id)
                    self._json({"point": repo.merged(p, repo.get_record(point_id))})
                    return

                m = re.fullmatch(r"/api/points/(\d+)/review", path)
                if m:
                    point_id = int(m.group(1))
                    rating = str(self._body().get("rating", ""))
                    if rating not in RATINGS:
                        self._error(400, f"rating 必须是 {'/'.join(RATINGS)}")
                        return
                    if repo.get_record(point_id) is None:
                        self._error(404, "该知识点还没有学习记录")
                        return
                    # 读-改-写 + 追加日志在同一事务内完成（见 repository.apply_review）
                    updated = repo.apply_review(point_id, rating)
                    self._json({"point": repo.merged(repo.get_point(point_id), updated)})
                    return

                if path == "/api/points":
                    body = self._body()
                    p = repo.add_point(
                        name=str(body.get("name", "")),
                        category=str(body.get("category", "未分类")),
                        principle=str(body.get("principle", "")),
                        visualization=str(body.get("visualization", "")),
                        tags=body.get("tags") or [],
                    )
                    self._json({"point": repo.merged(p, None)}, status=201)
                    return

                self._error(404, "接口不存在")
            except RepositoryError as e:
                self._repo_error(e)
            except Exception as e:
                self._internal_error(e)

        def do_DELETE(self):
            if not self._check_auth():
                return
            path = urlparse(self.path).path
            try:
                m = re.fullmatch(r"/api/points/(\d+)/record", path)
                if m:
                    removed = repo.reset_point(int(m.group(1)))
                    self._json({"ok": True, "removed": removed})
                    return
                self._error(404, "接口不存在")
            except RepositoryError as e:
                self._repo_error(e)
            except Exception as e:
                self._internal_error(e)

        # ------------------------------------------------------------ 辅助 --
        @staticmethod
        def _parse_int(value, field: str) -> int:
            try:
                return int(value)
            except (TypeError, ValueError) as exc:
                raise ValidationError(f"{field} 必须是整数") from exc

    return UraniaRequestHandler
