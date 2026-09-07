#!/bin/bash
# Urania 一键启动脚本
# 用法: ./run.sh [任意传给 main.py 的参数，如 --browser / --port 9000 / --reset]
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ 未找到 python3。请先安装: xcode-select --install 或 https://www.python.org/downloads/"
  exit 1
fi

exec python3 main.py "$@"
