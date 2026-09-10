"""py2app 打包配置：把 Urania 打成自包含的 .app（内嵌 Python 运行时）。

用法：
    python3 setup.py py2app          # 构建到 dist/Urania.app
    ./scripts/make_app.sh            # 推荐：先生成图标再构建，并做 ad-hoc 签名

打包后：
- 代码与 frontend/、种子数据都在包内（只读资源，路径见 urania/config.RESOURCE_ROOT）
- 用户数据写到 ~/Library/Application Support/Urania（不放在包内，否则装进
  /Applications 后不可写）
- 目标机无需预装 Python
"""
from __future__ import annotations

import sys
from pathlib import Path

from setuptools import setup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from urania import config

ROOT = Path(__file__).resolve().parent


def resource_entries() -> list[tuple[str, list[str]]]:
    """把 frontend/ 与种子数据登记为 bundle 内的资源。"""
    entries: list[tuple[str, list[str]]] = []
    frontend = ROOT / "frontend"

    by_dir: dict[str, list[str]] = {}
    for path in sorted(frontend.rglob("*")):
        if not path.is_file() or path.suffix == ".icns":  # icns 通过 iconfile 使用
            continue
        rel_dir = path.relative_to(frontend).parent
        dest = "frontend" if str(rel_dir) == "." else f"frontend/{rel_dir}"
        by_dir.setdefault(dest, []).append(str(path.relative_to(ROOT)))

    entries.extend(sorted(by_dir.items()))
    entries.append(("data", ["data/seed_knowledge.json"]))
    return entries


# pywebview 为可选依赖：装了就打进包（原生窗口），没装则回退浏览器
optional_includes: list[str] = []
try:
    import webview  # noqa: F401

    optional_includes.append("webview")
except ImportError:
    print("[setup] 未安装 pywebview，打包后将以浏览器方式打开界面")

plist = {
    "CFBundleName": config.APP_NAME,
    "CFBundleDisplayName": config.APP_NAME,
    "CFBundleIdentifier": "com.gaia.urania",
    "CFBundleVersion": config.APP_VERSION,
    "CFBundleShortVersionString": config.APP_VERSION,
    "CFBundleInfoDictionaryVersion": "6.0",
    "LSMinimumSystemVersion": "11.0",
    "NSHighResolutionCapable": True,
    "LSApplicationCategoryType": "public.app-category.education",
}

setup(
    name=config.APP_NAME,
    version=config.APP_VERSION,
    app=["main.py"],
    data_files=resource_entries(),
    options={
        "py2app": {
            "argv_emulation": False,
            "iconfile": "frontend/assets/Urania.icns",
            "packages": ["urania"],
            "includes": optional_includes,
            "plist": plist,
            "excludes": ["tkinter", "unittest", "pydoc", "doctest"],
        }
    },
    setup_requires=["py2app"],
)
