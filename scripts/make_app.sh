#!/bin/bash
# 生成可双击运行的 Urania.app（放在 dist/ 下，可拖到「应用程序」或 Dock）。
# 说明：.app 内部记录的是本项目的绝对路径，项目文件夹移动位置后需重新执行本脚本。
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$PROJECT_DIR/dist/Urania.app"
CONTENTS="$APP_DIR/Contents"
VERSION="$(cd "$PROJECT_DIR" && python3 -c 'from urania import APP_VERSION; print(APP_VERSION)')"

rm -rf "$APP_DIR"
mkdir -p "$CONTENTS/MacOS" "$CONTENTS/Resources"

cat > "$CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>            <string>Urania</string>
    <key>CFBundleDisplayName</key>     <string>Urania</string>
    <key>CFBundleIdentifier</key>      <string>com.gaia.urania</string>
    <key>CFBundleVersion</key>         <string>$VERSION</string>
    <key>CFBundleShortVersionString</key> <string>$VERSION</string>
    <key>CFBundlePackageType</key>     <string>APPL</string>
    <key>CFBundleExecutable</key>      <string>Urania</string>
    <key>LSMinimumSystemVersion</key>  <string>11.0</string>
    <key>NSHighResolutionCapable</key> <true/>
    <key>NSSupportsAutomaticGraphicsSwitching</key> <true/>
</dict>
</plist>
PLIST

cat > "$CONTENTS/MacOS/Urania" <<LAUNCHER
#!/bin/bash
# 由 scripts/make_app.sh 生成，指向项目目录
cd "$PROJECT_DIR" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  osascript -e 'display alert "Urania 无法启动" message "未找到 python3。请先安装 Python 3（python.org 或 xcode-select --install）后重试。"' >/dev/null 2>&1 || true
  exit 1
fi
# 双击启动无终端可见，日志落盘便于排查
exec >> "$PROJECT_DIR/dist/Urania-run.log" 2>&1
exec python3 main.py "\$@"
LAUNCHER
chmod +x "$CONTENTS/MacOS/Urania"

echo "✅ 已生成 $APP_DIR"
echo "   双击运行，或拖入「应用程序」/ Dock。"
