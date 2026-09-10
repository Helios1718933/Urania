#!/usr/bin/env python3
"""Urania 应用入口：初始化数据库 → 启动本地 API → 打开界面。

默认尝试 pywebview 原生 macOS 窗口（若已安装），
否则自动用默认浏览器打开；--browser 可强制浏览器模式。

端口策略：若首选端口上已有本应用实例在运行，直接复用该实例并只打开界面
（避免双击 .app 多次时重复起服务 / 端口冲突崩溃）；否则自动向后尝试绑定。

用法：
    python3 main.py                 # 默认启动
    python3 main.py --browser       # 强制用浏览器打开
    python3 main.py --no-window     # 仅启动服务（无界面，调试用）
    python3 main.py --port 9000     # 指定端口
    python3 main.py --reset         # 清空学习记录与数据库后重新播种
"""
from __future__ import annotations

import argparse
import fcntl
import json
import logging
import socket
import threading
import urllib.request
import webbrowser

from urania import auth, config, db, seed
from urania.logging_setup import setup_logging
from urania.repository import KnowledgeRepository
from urania.server import create_server

logger = logging.getLogger("urania")


PORT_SCAN_RANGE = 20  # 首选端口被占用时，向后尝试的端口数
LOCK_PATH = config.DATA_DIR / "urania.lock"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="Urania", description="知识点点名册")
    parser.add_argument("--port", type=int, default=config.DEFAULT_PORT, help="HTTP 端口")
    parser.add_argument("--browser", action="store_true", help="强制用浏览器打开界面")
    parser.add_argument("--no-window", action="store_true", help="只启动服务，不打开任何界面")
    parser.add_argument("--reset", action="store_true", help="重置数据库（删除后重新播种）")
    parser.add_argument(
        "--lan", action="store_true",
        help="局域网模式：监听 0.0.0.0 并启用访问口令（手机浏览器可访问）",
    )
    return parser.parse_args()


def local_ip() -> str:
    """取本机在局域网中的地址（UDP connect 不会真正发包）。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return str(sock.getsockname()[0])
    except OSError:
        return config.DEFAULT_HOST
    finally:
        sock.close()


def probe_running_instance(port: int) -> bool:
    """探测端口上是否已是本应用（兜底手段；强制直连不走环境代理）。"""
    url = f"http://{config.DEFAULT_HOST}:{port}/api/health"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("app") == config.APP_NAME
    except Exception:
        return False


def acquire_instance_lock():
    """获取单实例文件锁。

    Returns:
        (lock_handle, port)：拿到锁 → 本进程作为服务端，handle 需保持打开到进程退出，
        起服务后调用 write_port_to_lock() 写入实际端口；
        拿不到锁 → (None, 运行中实例写入的端口或 None)，本进程只打开界面。
    """
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    # 有意不用 with：锁句柄必须活到进程退出，提前关闭会释放 flock
    fh = open(LOCK_PATH, "a+")  # noqa: SIM115
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.seek(0)
        content = fh.read().strip()
        fh.close()
        port = int(content) if content.isdigit() else None
        return None, port
    fh.seek(0)
    fh.truncate()  # 清掉历史残留端口
    return fh, None


def write_port_to_lock(lock_fh, port: int) -> None:
    lock_fh.seek(0)
    lock_fh.truncate()
    lock_fh.write(str(port))
    lock_fh.flush()


def pick_free_port(preferred: int, host: str = config.DEFAULT_HOST) -> int:
    """选一个可用端口：跳过已被本应用占用（探测）或外服务占用（绑定失败）的端口。

    注意 macOS 上 SO_REUSEADDR 允许重复绑定，绑定不会报错，因此必须先探测。
    """
    for port in range(preferred, preferred + PORT_SCAN_RANGE):
        if probe_running_instance(port):
            logger.info("端口 %d 上已有本应用实例，跳过", port)
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
            except OSError:
                logger.info("端口 %d 被其他程序占用，尝试下一个", port)
                continue
        return port
    raise SystemExit(f"端口 {preferred}~{preferred + PORT_SCAN_RANGE - 1} 均被占用，无法启动")


def open_native_window(url: str) -> bool:
    """尝试用 pywebview 打开原生窗口；未安装则返回 False。"""
    try:
        import webview
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
    setup_logging()
    args = parse_args()

    # ---- 单实例判定：文件锁是权威，网络探测只是兜底 ----
    lock_fh, running_port = acquire_instance_lock()
    if lock_fh is None:
        # 已有实例在跑：找到它的端口，只打开界面后退出
        port = running_port
        if port is None:
            for candidate in range(args.port, args.port + PORT_SCAN_RANGE):
                if probe_running_instance(candidate):
                    port = candidate
                    break
        if port is None:
            raise SystemExit("已有 Urania 实例在运行，但未能定位其端口；请稍后重试。")
        logger.info("检测到 Urania 已在运行: http://%s:%d —— 直接打开界面",
                    config.DEFAULT_HOST, port)
        url = f"http://{config.DEFAULT_HOST}:{port}"
        if not args.no_window and (args.browser or not open_native_window(url)):
            webbrowser.open(url)
        return 0

    # ---- 本进程作为服务端 ----
    if args.reset:
        backup = db.backup_database(config.DB_PATH)
        if backup is not None:
            logger.info("重置前已备份数据库: %s", backup)
        if config.DB_PATH.exists():
            config.DB_PATH.unlink()
            logger.info("已删除旧数据库: %s", config.DB_PATH)

    # 旧版数据搬迁（幂等）：项目 data/ → ~/Library/Application Support/Urania
    moved = db.migrate_legacy_data()
    if moved:
        logger.info("已迁移旧数据到 %s：%s", config.DATA_DIR, "、".join(moved))

    conn = db.init(config.DB_PATH)
    repo = KnowledgeRepository(conn)
    seed.seed_if_needed(repo)

    # 局域网模式：监听所有网卡并强制要求访问口令
    host = "0.0.0.0" if args.lan else config.DEFAULT_HOST
    auth_token = auth.load_or_create_token(config.TOKEN_FILE) if args.lan else None

    port = pick_free_port(args.port, host=host)
    server = create_server(repo, host=host, port=port, auth_token=auth_token)
    write_port_to_lock(lock_fh, port)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="urania-http")
    thread.start()

    local_url = f"http://{config.DEFAULT_HOST}:{port}"
    logger.info("%s v%s 已启动", config.APP_NAME, config.APP_VERSION)
    logger.info("  本机访问: %s", local_url)
    if args.lan:
        logger.info("  手机访问: http://%s:%d", local_ip(), port)
        logger.info("  访问口令: %s   （首次打开会要求输入，之后自动记住）", auth_token)
        logger.info("  提示: 首次在手机上打开后可用「添加到桌面」生成图标")
    else:
        logger.info("  提示: 需要手机访问请用 --lan 启动")

    try:
        if args.no_window:
            thread.join()
        elif args.browser:
            webbrowser.open(local_url)
            thread.join()
        elif not open_native_window(local_url):
            logger.info("未安装 pywebview（可选依赖），已用浏览器打开。"
                        "如需原生窗口: pip install 'pywebview[qt]' 或 pip install pywebview pyobjc")
            webbrowser.open(local_url)
            thread.join()
    except KeyboardInterrupt:
        logger.info("收到退出信号")
    finally:
        server.shutdown()
        lock_fh.close()
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
