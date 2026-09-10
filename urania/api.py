"""REST API + 前端静态文件服务（标准库 http.server，零依赖）。

路由一览：
    GET    /api/health                 存活检查
    GET    /api/config                 前端需要的领域常量（掌握度标签、自评档位）
    GET    /api/stats                  学习统计
    GET    /api/draw                   随机抽取一个未学习知识点（核心功能，不改变状态）
    POST   /api/points                 新增知识点 {name, category, principle, visualization, tags}
    GET    /api/points                 全部知识点（含学习状态）
    GET    /api/points/{id}            知识点详情
    POST   /api/points/{id}/learn      标记已学习 {mastery: 1~3}
    POST   /api/points/{id}/review     提交一次复习自评 {rating: forgot|fuzzy|solid}
    DELETE /api/points/{id}/record     删除学习记录（重置为未学习）
    GET    /api/review/queue           复习队列（到期优先，按掌握度升序）
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse

from . import config, migrations, sampler
from .repository import KnowledgeRepository, RepositoryError
from .review import RATINGS, RATING_LABELS

_STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


def make_handler(repo: KnowledgeRepository):
    class UraniaRequestHandler(BaseHTTPRequestHandler):
        server_version = f"Urania/{config.APP_VERSION}"
        protocol_version = "HTTP/1.1"

        # -------------------------------------------------------- 工具方法 --
        def log_message(self, fmt, *args):  # 安静一些，只记录错误
            pass

        def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store" if content_type.startswith("application/json") else "no-cache")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, status: int = 200) -> None:
            self._send(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8", status)

        def _error(self, status: int, message: str) -> None:
            self._json({"error": message}, status)

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length == 0:
                return {}
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise RepositoryError("请求体不是合法的 JSON")

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

        # -------------------------------------------------------- 路由 --
        def do_GET(self):  # noqa: N802
            path = urlparse(self.path).path
            try:
                if path in ("/", "/index.html"):
                    self._static("index.html")
                elif path.startswith(("/css/", "/js/", "/assets/")):
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
                    point = sampler.draw_unlearned(repo.unlearned_points())
                    self._json({"point": repo.merged(point, None) if point else None,
                                "remaining": len(repo.unlearned_points())})
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
                self._error(404, str(e))
            except Exception as e:  # noqa: BLE001
                self._error(500, f"服务器内部错误: {e}")

        def do_POST(self):  # noqa: N802
            path = urlparse(self.path).path
            try:
                m = re.fullmatch(r"/api/points/(\d+)/learn", path)
                if m:
                    point_id = int(m.group(1))
                    mastery = int(self._body().get("mastery", 1))
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
                self._error(400, str(e))
            except Exception as e:  # noqa: BLE001
                self._error(500, f"服务器内部错误: {e}")

        def do_DELETE(self):  # noqa: N802
            path = urlparse(self.path).path
            try:
                m = re.fullmatch(r"/api/points/(\d+)/record", path)
                if m:
                    repo.reset_point(int(m.group(1)))
                    self._json({"ok": True})
                else:
                    self._error(404, "接口不存在")
            except Exception as e:  # noqa: BLE001
                self._error(500, f"服务器内部错误: {e}")

    return UraniaRequestHandler
