#!/usr/bin/env python3
"""Urania 应用入口：初始化数据库 → 启动本地 API → 打开界面。

默认尝试 pywebview 原生 macOS 窗口（若已安装），
否则自动用默认浏览器打开；--browser 可强制浏览器模式。

用法：
    python3 main.py                 # 默认启动
    python3 main.py --browser       # 强制用浏览器打开
    python3 main.py --no-window     # 仅启动服务（无界面，调试用）
    python3 main.py --port 9000     # 指定端口
    python3 main.py --reset         # 清空学习记录与数据库后重新播种
"""
from __future__ import annotations

import argparse
import logging
import threading
import webbrowser

import urania
from urania import config, db, seed
from urania.repository import KnowledgeRepository
from urania.server import create_server

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger("urania")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="Urania", description="知识点点名册")
    parser.add_argument("--port", type=int, default=config.DEFAULT_PORT, help="HTTP 端口")
    parser.add_argument("--browser", action="store_true", help="强制用浏览器打开界面")
    parser.add_argument("--no-window", action="store_true", help="只启动服务，不打开任何界面")
    parser.add_argument("--reset", action="store_true", help="重置数据库（删除后重新播种）")
    return parser.parse_args()


def open_native_window(url: str) -> bool:
    """尝试用 pywebview 打开原生窗口；未安装则返回 False。"""
    try:
        import webview  # noqa: PLC0415
    except ImportError:
        return False
    webview.create_window(
        f"{config.APP_NAME} · 知识点点名册", url,
        width=1180, height=780, min_size=(960, 620),
        background_color="#F5F5F7",
    )
    webview.start()  # 阻塞直到窗口关闭
    return True


def main() -> int:
    args = parse_args()

    if args.reset and config.DB_PATH.exists():
        config.DB_PATH.unlink()
        logger.info("已删除旧数据库: %s", config.DB_PATH)

    conn = db.init(config.DB_PATH)
    repo = KnowledgeRepository(conn)
    seed.seed_if_needed(repo)

    server = create_server(repo, port=args.port)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="urania-http")
    thread.start()
    url = f"http://{config.DEFAULT_HOST}:{server.server_address[1]}"
    logger.info("%s v%s 已启动: %s", config.APP_NAME, config.APP_VERSION, url)

    try:
        if args.no_window:
            thread.join()
        elif args.browser:
            webbrowser.open(url)
            thread.join()
        elif not open_native_window(url):
            logger.info("未安装 pywebview（可选依赖），已用浏览器打开。"
                        "如需原生窗口: pip install 'pywebview[qt]' 或 pip install pywebview pyobjc")
            webbrowser.open(url)
            thread.join()
    except KeyboardInterrupt:
        logger.info("收到退出信号")
    finally:
        server.shutdown()
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
