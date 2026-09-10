#!/bin/bash
# 生成自包含的 Urania.app（内嵌 Python 运行时，目标 Mac 无需预装 Python）。
#
# 用法:
#   ./scripts/make_app.sh
#
# 说明:
# - 首次运行会自动创建 build/venv 并安装 py2app / pywebview（较慢，之后走缓存）
# - 打包后资源（frontend、种子数据）在包内；用户数据写到
#   ~/Library/Application Support/Urania
# - 用 ad-hoc 签名（本机自用足够）；对外分发需 Developer ID + 公证
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

BUILD_VENV="$PROJECT_DIR/build/venv"

if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ 未找到 python3；打包机需要 Python 3.10+（目标机不需要）"
  exit 1
fi

echo "▶ 1/4 生成图标（含 .icns）"
python3 scripts/make_icons.py | tail -2

if [ ! -x "$BUILD_VENV/bin/python" ]; then
  echo "▶ 创建构建环境（首次运行，需要几分钟）"
  python3 -m venv "$BUILD_VENV"
  "$BUILD_VENV/bin/pip" install --quiet --upgrade pip
fi

echo "▶ 2/4 安装打包依赖"
"$BUILD_VENV/bin/pip" install --quiet py2app pywebview pyobjc

echo "▶ 3/4 构建 .app"
rm -rf "$PROJECT_DIR/build/Urania.app" "$PROJECT_DIR/dist/Urania.app"
"$BUILD_VENV/bin/python" setup.py py2app > "$PROJECT_DIR/build/py2app.log" 2>&1

if [ ! -d "$PROJECT_DIR/dist/Urania.app" ]; then
  echo "❌ 构建失败，日志见 build/py2app.log"
  tail -20 "$PROJECT_DIR/build/py2app.log"
  exit 1
fi

echo "▶ 4/4 ad-hoc 签名"
codesign --force --deep --sign - "$PROJECT_DIR/dist/Urania.app" 2>/dev/null \
  || echo "  （签名失败，未签名的应用首次打开需右键→打开）"

SIZE="$(du -sh "$PROJECT_DIR/dist/Urania.app" | cut -f1)"
echo
echo "✅ 已生成 dist/Urania.app（${SIZE}）"
echo "   双击即可运行，目标 Mac 无需预装 Python。"
echo "   首次打开若被 Gatekeeper 拦截：右键 → 打开。"
