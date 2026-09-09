#!/bin/bash
# 生成 macOS 标准安装包 dist/Urania_<版本号>.dmg
# 双击 DMG → 把 Urania.app 拖入右侧 Applications 文件夹即完成「安装」。
# 注意：Urania.app 内记录的是本项目文件夹的绝对路径（Python 源码与数据库都在项目里），
#       项目文件夹移动/重命名后需重新执行本脚本生成新的安装包。
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# 1) 先生成最新的 .app
"$PROJECT_DIR/scripts/make_app.sh"

# 2) 组装 DMG 暂存目录：Urania.app + Applications 文件夹替身（拖拽安装）
VERSION="$(python3 -c 'from urania import APP_VERSION; print(APP_VERSION)')"
STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT
cp -R "$PROJECT_DIR/dist/Urania.app" "$STAGING/"
ln -s /Applications "$STAGING/Applications"

# 3) 压制 DMG（UDZO：HFS+ 压缩镜像，兼容性最好）
DMG="$PROJECT_DIR/dist/Urania_${VERSION}.dmg"
rm -f "$DMG"
hdiutil create -volname "Urania" -srcfolder "$STAGING" -ov -format UDZO "$DMG" >/dev/null

echo "✅ 安装包已生成: $DMG"
echo "   双击 DMG 打开，把 Urania.app 拖入 Applications 即完成安装。"
