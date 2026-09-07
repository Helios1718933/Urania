#!/bin/bash
# 重置数据库：删除 SQLite 文件并按种子数据重新初始化（知识点恢复初始，学习记录清空）。
set -euo pipefail
cd "$(dirname "$0")/.."

python3 - <<'PY'
from urania import config, db, seed
from urania.repository import KnowledgeRepository

if config.DB_PATH.exists():
    config.DB_PATH.unlink()
    print(f"已删除旧数据库: {config.DB_PATH}")
conn = db.init(config.DB_PATH)
n = seed.seed_if_needed(KnowledgeRepository(conn))
print(f"已按种子数据重新导入 {n} 个知识点。")
PY
